mod protocol;

use protocol::{Request, Response};
use serde_json::{json, Value};
use std::collections::HashSet;
use std::fs;
use std::io::{self, Read, Write};
use std::path::Path;
use std::process::Command;
use std::thread;
use std::time::Duration;

const MAX_LABEL_LEN: usize = 64;

#[derive(Debug, Clone)]
struct VideoParams {
    video_nr: i64,
    label: String,
    exclusive_caps: bool,
    force: bool,
    always_reload: bool,
}

#[derive(Debug, Clone)]
struct V4l2Inspect {
    module_loaded: bool,
    device: String,
    device_exists: bool,
    device_busy: bool,
    config_matches: bool,
    requires_reload: bool,
    slot_index: Option<usize>,
    reasons: Vec<String>,
}

impl V4l2Inspect {
    fn to_json(&self) -> Value {
        json!({
            "module_loaded": self.module_loaded,
            "device": self.device,
            "device_exists": self.device_exists,
            "device_busy": self.device_busy,
            "config_matches": self.config_matches,
            "requires_reload": self.requires_reload,
            "slot_index": self.slot_index,
            "reasons": self.reasons,
        })
    }
}

fn write_response(resp: &Response) {
    let mut stdout = io::stdout();
    let payload = serde_json::to_string(resp).unwrap_or_else(|_| {
        "{\"ok\":false,\"error\":{\"code\":\"E_SERIALIZE\",\"message\":\"serialization failure\"}}".to_string()
    });
    let _ = stdout.write_all(payload.as_bytes());
}

fn parse_bool(params: &Value, key: &str, default: bool) -> Result<bool, String> {
    match params.get(key) {
        None => Ok(default),
        Some(v) => v
            .as_bool()
            .ok_or_else(|| format!("{} must be a boolean", key)),
    }
}

fn parse_i64(params: &Value, key: &str, default: i64) -> Result<i64, String> {
    match params.get(key) {
        None => Ok(default),
        Some(v) => v
            .as_i64()
            .ok_or_else(|| format!("{} must be an integer", key)),
    }
}

fn parse_string(params: &Value, key: &str, default: &str) -> Result<String, String> {
    match params.get(key) {
        None => Ok(default.to_string()),
        Some(v) => v
            .as_str()
            .map(|s| s.to_string())
            .ok_or_else(|| format!("{} must be a string", key)),
    }
}

fn validate_param_keys(params: &Value, allowed: &[&str]) -> Result<(), String> {
    let obj = params
        .as_object()
        .ok_or_else(|| "params must be an object".to_string())?;
    let allowed_set: HashSet<&str> = allowed.iter().copied().collect();
    for key in obj.keys() {
        if !allowed_set.contains(key.as_str()) {
            return Err(format!("unsupported param: {}", key));
        }
    }
    Ok(())
}

fn validate_request_id(request_id: &str) -> Result<(), String> {
    if request_id.is_empty() || request_id.len() > 128 {
        return Err("request_id must be 1..128 chars".to_string());
    }
    if request_id
        .chars()
        .all(|c| c.is_ascii_alphanumeric() || c == '-' || c == '_' || c == '.')
    {
        Ok(())
    } else {
        Err("request_id contains unsupported characters".to_string())
    }
}

fn valid_label(label: &str) -> bool {
    if label.is_empty() || label.len() > MAX_LABEL_LEN {
        return false;
    }
    label
        .chars()
        .all(|c| c.is_ascii_alphanumeric() || c == ' ' || c == '_' || c == '-')
}

fn parse_video_params(params: &Value) -> Result<VideoParams, String> {
    validate_param_keys(
        params,
        &[
            "video_nr",
            "label",
            "exclusive_caps",
            "force",
            "always_reload",
        ],
    )?;
    let video_nr = parse_i64(params, "video_nr", 10)?;
    if !(0..=255).contains(&video_nr) {
        return Err("video_nr must be in range 0..255".to_string());
    }
    let label = parse_string(params, "label", "AVream Camera")?;
    if !valid_label(&label) {
        return Err("label must be 1..64 chars and use [A-Za-z0-9 _-]".to_string());
    }
    Ok(VideoParams {
        video_nr,
        label,
        exclusive_caps: parse_bool(params, "exclusive_caps", true)?,
        force: parse_bool(params, "force", false)?,
        always_reload: parse_bool(params, "always_reload", false)?,
    })
}

fn parse_empty_params(params: &Value) -> Result<(), String> {
    validate_param_keys(params, &[])
}

fn cmd_exists(cmd: &str) -> bool {
    std::env::var("PATH")
        .ok()
        .map(|paths| {
            paths
                .split(':')
                .map(Path::new)
                .map(|base| base.join(cmd))
                .any(|p| p.exists())
        })
        .unwrap_or(false)
}

fn run_cmd(cmd: &str, args: &[String]) -> Result<(), String> {
    if !cmd_exists(cmd) {
        return Err(format!("{} not found in PATH", cmd));
    }
    let status = Command::new(cmd)
        .args(args)
        .status()
        .map_err(|e| format!("failed to run {}: {}", cmd, e))?;
    if status.success() {
        Ok(())
    } else {
        Err(format!("{} exited with status {}", cmd, status))
    }
}

fn ensure_config(video_nr: i64, label: &str, exclusive_caps: bool) -> Result<Value, String> {
    if !(0..=255).contains(&video_nr) {
        return Err("video_nr out of range (0-255)".to_string());
    }

    let path = "/etc/modprobe.d/avream-v4l2loopback.conf";
    let content = format!(
        "# Managed by AVream\noptions v4l2loopback video_nr={} card_label=\"{}\" exclusive_caps={}\n",
        video_nr,
        label,
        if exclusive_caps { 1 } else { 0 }
    );
    fs::write(path, content).map_err(|e| format!("failed to write {}: {}", path, e))?;
    Ok(json!({"config_path": path}))
}

fn device_busy(video_nr: i64) -> bool {
    let dev = format!("/dev/video{}", video_nr);
    let status = Command::new("fuser").arg(&dev).status();
    match status {
        Ok(s) => s.success(),
        Err(_) => false,
    }
}

fn module_loaded(module: &str) -> bool {
    if let Ok(text) = std::fs::read_to_string("/proc/modules") {
        for line in text.lines() {
            if line.starts_with(&format!("{} ", module)) {
                return true;
            }
        }
    }
    false
}

fn normalize_param_token(input: &str) -> String {
    input
        .trim()
        .trim_matches('"')
        .trim_matches('\'')
        .trim()
        .to_string()
}

fn split_param_csv(raw: &str) -> Vec<String> {
    raw.trim()
        .split(',')
        .map(normalize_param_token)
        .filter(|s| !s.is_empty())
        .collect()
}

fn parse_bool_token(raw: &str) -> Option<bool> {
    let v = raw.trim().to_ascii_lowercase();
    match v.as_str() {
        "1" | "y" | "yes" | "true" | "on" => Some(true),
        "0" | "n" | "no" | "false" | "off" => Some(false),
        _ => None,
    }
}

fn read_sys_param(path: &str) -> Option<String> {
    fs::read_to_string(path).ok()
}

fn inspect_v4l2(video_nr: i64, label: &str, exclusive_caps: bool) -> V4l2Inspect {
    let device = format!("/dev/video{}", video_nr);
    let module_loaded = module_loaded("v4l2loopback");
    let device_exists = Path::new(&device).exists();
    let device_busy = device_exists && device_busy(video_nr);

    let mut reasons: Vec<String> = Vec::new();
    let mut slot_index: Option<usize> = None;
    let mut config_matches = false;

    if !module_loaded {
        reasons.push("module_not_loaded".to_string());
    } else {
        let nr_raw = read_sys_param("/sys/module/v4l2loopback/parameters/video_nr");
        let labels_raw = read_sys_param("/sys/module/v4l2loopback/parameters/card_label");
        let excl_raw = read_sys_param("/sys/module/v4l2loopback/parameters/exclusive_caps");

        if nr_raw.is_none() {
            reasons.push("video_nr_param_unavailable".to_string());
        }

        let nr_values = nr_raw.map(|v| split_param_csv(&v)).unwrap_or_default();
        let label_values = labels_raw.map(|v| split_param_csv(&v)).unwrap_or_default();
        let excl_values = excl_raw.map(|v| split_param_csv(&v)).unwrap_or_default();

        let target_nr = video_nr.to_string();
        slot_index = nr_values.iter().position(|v| v == &target_nr);
        if slot_index.is_none() {
            reasons.push("video_nr_not_configured".to_string());
        } else {
            let idx = slot_index.unwrap_or_default();
            let mut label_ok = true;
            let mut excl_ok = true;

            if let Some(current_label) = label_values.get(idx) {
                if current_label != label {
                    label_ok = false;
                    reasons.push("label_mismatch".to_string());
                }
            }

            if let Some(current_excl) = excl_values.get(idx) {
                match parse_bool_token(current_excl) {
                    Some(parsed) if parsed == exclusive_caps => {}
                    _ => {
                        excl_ok = false;
                        reasons.push("exclusive_caps_mismatch".to_string());
                    }
                }
            }

            config_matches = label_ok && excl_ok;
        }
    }

    if !device_exists {
        reasons.push("device_missing".to_string());
    }

    let requires_reload = !module_loaded || !device_exists || !config_matches;

    V4l2Inspect {
        module_loaded,
        device,
        device_exists,
        device_busy,
        config_matches,
        requires_reload,
        slot_index,
        reasons,
    }
}

fn wait_for_device(video_nr: i64, retries: usize, delay_ms: u64) -> bool {
    let dev = format!("/dev/video{}", video_nr);
    for _ in 0..retries {
        if Path::new(&dev).exists() {
            return true;
        }
        thread::sleep(Duration::from_millis(delay_ms));
    }
    Path::new(&dev).exists()
}

fn modprobe_load(video_nr: i64, label: &str, exclusive_caps: bool) -> Result<(), String> {
    let args = vec![
        "v4l2loopback".to_string(),
        format!("video_nr={}", video_nr),
        format!("card_label={}", label),
        format!("exclusive_caps={}", if exclusive_caps { 1 } else { 0 }),
    ];
    run_cmd("modprobe", &args)
}

fn modprobe_unload() -> Result<(), String> {
    let args = vec!["-r".to_string(), "v4l2loopback".to_string()];
    run_cmd("modprobe", &args)
}

fn handle_request(req: &Request) -> Response {
    let params = &req.params;

    match req.action.as_str() {
        "noop" => {
            if let Err(e) = parse_empty_params(params) {
                return Response::err("E_INVALID_PARAM", &e);
            }
            Response::ok(json!({"noop": true}))
        }
        "v4l2.status" => {
            let parsed = match parse_video_params(params) {
                Ok(p) => p,
                Err(e) => return Response::err("E_INVALID_PARAM", &e),
            };
            let status = inspect_v4l2(parsed.video_nr, &parsed.label, parsed.exclusive_caps);
            Response::ok(status.to_json())
        }
        "snd_aloop.status" => {
            if let Err(e) = parse_empty_params(params) {
                return Response::err("E_INVALID_PARAM", &e);
            }
            let loaded = module_loaded("snd_aloop");
            Response::ok(json!({"module_loaded": loaded, "module": "snd_aloop"}))
        }
        "v4l2.ensure_config" => {
            let parsed = match parse_video_params(params) {
                Ok(p) => p,
                Err(e) => return Response::err("E_INVALID_PARAM", &e),
            };
            match ensure_config(parsed.video_nr, &parsed.label, parsed.exclusive_caps) {
                Ok(data) => Response::ok(data),
                Err(e) => Response::err("E_CONFIG_WRITE", &e),
            }
        }
        "v4l2.load" => {
            let parsed = match parse_video_params(params) {
                Ok(p) => p,
                Err(e) => return Response::err("E_INVALID_PARAM", &e),
            };
            match modprobe_load(parsed.video_nr, &parsed.label, parsed.exclusive_caps) {
                Ok(_) => Response::ok(json!({"loaded": true})),
                Err(e) => {
                    if e.contains("not found") {
                        Response::err("E_MODPROBE_NOT_FOUND", &e)
                    } else {
                        Response::err("E_MODPROBE", &e)
                    }
                }
            }
        }
        "v4l2.reload" => {
            let parsed = match parse_video_params(params) {
                Ok(p) => p,
                Err(e) => return Response::err("E_INVALID_PARAM", &e),
            };
            let before = inspect_v4l2(parsed.video_nr, &parsed.label, parsed.exclusive_caps);

            if before.device_busy && !parsed.force {
                if !before.requires_reload && !parsed.always_reload {
                    return Response::ok(json!({
                        "reloaded": false,
                        "ensured": true,
                        "reason": "busy_but_already_ready",
                        "always_reload": parsed.always_reload,
                        "status_before": before.to_json(),
                    }));
                }
                return Response::err(
                    "E_BUSY_DEVICE",
                    "target /dev/video device is busy and requires reload",
                );
            }

            if !before.requires_reload && !parsed.always_reload {
                let _ = ensure_config(parsed.video_nr, &parsed.label, parsed.exclusive_caps);
                return Response::ok(json!({
                    "reloaded": false,
                    "ensured": true,
                    "reason": "already_ready",
                    "always_reload": parsed.always_reload,
                    "status_before": before.to_json(),
                }));
            }

            match ensure_config(parsed.video_nr, &parsed.label, parsed.exclusive_caps) {
                Ok(_) => {}
                Err(e) => return Response::err("E_CONFIG_WRITE", &e),
            }

            if before.module_loaded {
                let _ = modprobe_unload();
            }

            match modprobe_load(parsed.video_nr, &parsed.label, parsed.exclusive_caps) {
                Ok(_) => {
                    let appeared = wait_for_device(parsed.video_nr, 30, 100);
                    if !appeared {
                        return Response::err(
                            "E_DEVICE_MISSING",
                            "reloaded module but target /dev/videoN did not appear",
                        );
                    }
                    let after = inspect_v4l2(parsed.video_nr, &parsed.label, parsed.exclusive_caps);
                    if !after.config_matches {
                        return Response::err("E_CONFIG_MISMATCH", "v4l2loopback loaded but effective params do not match requested config");
                    }
                    Response::ok(json!({
                        "reloaded": true,
                        "ensured": true,
                        "always_reload": parsed.always_reload,
                        "video_nr": parsed.video_nr,
                        "status_before": before.to_json(),
                        "status_after": after.to_json(),
                    }))
                }
                Err(e) => {
                    if e.contains("not found") {
                        Response::err("E_MODPROBE_NOT_FOUND", &e)
                    } else {
                        Response::err("E_MODPROBE", &e)
                    }
                }
            }
        }
        "snd_aloop.load" => {
            if let Err(e) = parse_empty_params(params) {
                return Response::err("E_INVALID_PARAM", &e);
            }
            match run_cmd("modprobe", &["snd_aloop".to_string()]) {
                Ok(_) => Response::ok(json!({"loaded": true, "module": "snd_aloop"})),
                Err(e) => Response::err("E_MODPROBE", &e),
            }
        }
        "snd_aloop.unload" => {
            if let Err(e) = parse_empty_params(params) {
                return Response::err("E_INVALID_PARAM", &e);
            }
            match run_cmd("modprobe", &["-r".to_string(), "snd_aloop".to_string()]) {
                Ok(_) => Response::ok(json!({"unloaded": true, "module": "snd_aloop"})),
                Err(e) => Response::err("E_MODPROBE", &e),
            }
        }
        _ => Response::err("E_ACTION", "unsupported action"),
    }
}

fn main() {
    let mut input = String::new();
    if io::stdin().read_to_string(&mut input).is_err() {
        write_response(&Response::err("E_INPUT", "failed to read stdin"));
        return;
    }

    let req: Request = match serde_json::from_str(&input) {
        Ok(v) => v,
        Err(_) => {
            write_response(&Response::err("E_JSON", "invalid json request"));
            return;
        }
    };

    // Keep request_id consumed/validated to avoid accidental schema drift.
    if let Err(e) = validate_request_id(req.request_id.trim()) {
        write_response(&Response::err("E_REQUEST", &e));
        return;
    }

    if !Path::new("/etc").exists() {
        write_response(&Response::err("E_ENV", "invalid runtime environment"));
        return;
    }

    let resp = handle_request(&req);
    write_response(&resp);
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn test_valid_label() {
        assert!(valid_label("AVream Camera"));
        assert!(valid_label("AVream_Cam-1"));
        assert!(!valid_label(""));
        assert!(!valid_label("bad/label"));
    }

    #[test]
    fn test_parse_video_params_invalid_range() {
        let params = json!({"video_nr": 999});
        let err = parse_video_params(&params).err().unwrap();
        assert!(err.contains("range"));
    }

    #[test]
    fn test_parse_video_params_defaults() {
        let params = json!({});
        let parsed = parse_video_params(&params).unwrap();
        assert_eq!(parsed.video_nr, 10);
        assert_eq!(parsed.label, "AVream Camera");
        assert!(parsed.exclusive_caps);
        assert!(!parsed.force);
        assert!(!parsed.always_reload);
    }

    #[test]
    fn test_parse_video_params_rejects_unknown_key() {
        let params = json!({"video_nr": 10, "oops": true});
        let err = parse_video_params(&params).err().unwrap();
        assert!(err.contains("unsupported param"));
    }

    #[test]
    fn test_noop_rejects_params() {
        let req = Request {
            request_id: "rid-1".to_string(),
            action: "noop".to_string(),
            params: json!({"x": 1}),
        };
        let resp = handle_request(&req);
        assert!(!resp.ok);
    }

    #[test]
    fn test_request_id_validation() {
        assert!(validate_request_id("a-b_c.123").is_ok());
        assert!(validate_request_id("").is_err());
        assert!(validate_request_id("bad id").is_err());
    }

    #[test]
    fn test_parse_video_params_rejects_wrong_types() {
        let params = json!({"video_nr": "10", "exclusive_caps": "true"});
        let err = parse_video_params(&params).err().unwrap();
        assert!(err.contains("must be"));
    }

    #[test]
    fn test_split_param_csv_strips_quotes_and_spaces() {
        let vals = split_param_csv(" 10 , \"AVream Camera\" , 1 ");
        assert_eq!(vals, vec!["10", "AVream Camera", "1"]);
    }

    #[test]
    fn test_parse_bool_token_variants() {
        assert_eq!(parse_bool_token("1"), Some(true));
        assert_eq!(parse_bool_token("Y"), Some(true));
        assert_eq!(parse_bool_token("true"), Some(true));
        assert_eq!(parse_bool_token("0"), Some(false));
        assert_eq!(parse_bool_token("N"), Some(false));
        assert_eq!(parse_bool_token("false"), Some(false));
        assert_eq!(parse_bool_token("maybe"), None);
    }
}
