mod dependencies;
use std::{
    env, fs,
    os::unix::{fs::PermissionsExt, process::CommandExt},
    path::PathBuf,
    process::{self, Command},
};
include!(concat!(env!("OUT_DIR"), "/bundle.rs"));

fn home() -> Result<PathBuf, String> {
    env::var_os("HOME")
        .map(PathBuf::from)
        .filter(|p| p.is_absolute())
        .ok_or_else(|| "HOME must be an absolute path".into())
}
fn share() -> Result<PathBuf, String> {
    Ok(home()?.join(".local/share/hyperterminal"))
}
fn extract() -> Result<PathBuf, String> {
    let parent = share()?.join("runtime");
    fs::create_dir_all(&parent).map_err(|e| e.to_string())?;
    fs::set_permissions(&parent, fs::Permissions::from_mode(0o700)).map_err(|e| e.to_string())?;
    let directory = parent.join(BUNDLE_ID);
    fs::create_dir_all(&directory).map_err(|e| e.to_string())?;
    for (name, data) in FILES {
        let path = directory.join(name);
        fs::create_dir_all(path.parent().unwrap()).map_err(|e| e.to_string())?;
        fs::write(&path, data).map_err(|e| e.to_string())?;
        fs::set_permissions(
            &path,
            fs::Permissions::from_mode(if name.starts_with("bin/") {
                0o755
            } else {
                0o644
            }),
        )
        .map_err(|e| e.to_string())?;
    }
    Ok(directory)
}
fn installed() -> Result<bool, String> {
    let bin = home()?.join(".local/bin");
    Ok(fs::read_to_string(share()?.join("bundle-version"))
        .ok()
        .as_deref()
        == Some(BUNDLE_ID)
        && [
            "hyperterminal-start",
            "hyperterminal-tab",
            "hyperterminal-session",
            "hyperterminal-catalog",
            "hyperterminal-agent-runner",
        ]
        .iter()
        .all(|name| bin.join(name).is_file()))
}
fn deploy(no_activate: bool) -> Result<(), String> {
    let directory = extract()?;
    let executable = env::current_exe().map_err(|e| e.to_string())?;
    let mut command = Command::new("python3");
    command
        .arg(directory.join("install.py"))
        .env("HYPERTERMINAL_BINARY_SOURCE", executable);
    if no_activate {
        command.arg("--no-activate");
    }
    let status = command.status().map_err(|e| e.to_string())?;
    if !status.success() {
        return Err(format!(
            "HyperTerminal deployment failed ({status}). Existing sessions were not terminated."
        ));
    }
    fs::write(share()?.join("bundle-version"), BUNDLE_ID).map_err(|e| e.to_string())?;
    Ok(())
}
fn usage() {
    println!("HyperTerminal {}\n\nUsage: hyperterminal [COMMAND]\n\n  start                 Check dependencies and open HyperTerminal (default)\n  install [--no-activate] Check dependencies and deploy embedded desktop files\n  doctor / --check       Report dependencies without changing anything\n  agents [list|history]  Detect installed agents or list previous conversations\n  sessions COMMAND      Manage persistent sessions (list, list-saved, create, ...)\n  selector              Open the agent/session selector\n  clipboard             Save clipboard image and copy its path\n  --version             Print binary version\n\nMissing dependencies are installed only after explicit confirmation.\nThis binary embeds the current Bash/Python runtime and SVG assets;\nYakuake, Konsole, tmux, system interpreters, and coding agents remain external.",env!("CARGO_PKG_VERSION"));
}
fn main_result() -> Result<i32, String> {
    let args: Vec<String> = env::args().skip(1).collect();
    let action = args.first().map(String::as_str).unwrap_or("start");
    match action {
        "--version" | "version" => {
            println!("HyperTerminal {} ({BUNDLE_ID})", env!("CARGO_PKG_VERSION"));
            return Ok(0);
        }
        "--help" | "-h" | "help" => {
            usage();
            return Ok(0);
        }
        "doctor" | "--check" => return Ok(if dependencies::doctor() { 0 } else { 1 }),
        "install" if args.iter().skip(1).any(|arg| arg != "--no-activate") => {
            return Err("Usage: hyperterminal install [--no-activate]".into())
        }
        "start" | "install" | "agents" | "sessions" | "selector" | "clipboard" => {}
        _ => return Err(format!("Unknown command: {action}. Use --help.")),
    }
    // Consent and successful dependency verification precede any runtime extraction.
    dependencies::ensure()?;
    if action == "install" {
        deploy(args.iter().any(|arg| arg == "--no-activate"))?;
        return Ok(0);
    }
    if !installed()? {
        if !dependencies::confirm("Deploy HyperTerminal's embedded runtime and desktop integration into your user account? Existing files will be backed up. Running sessions and saved session records will be preserved.")? {
            return Err("HyperTerminal setup declined. No user files were deployed.".into());
        }
        deploy(false)?;
    }
    let bin = home()?.join(".local/bin");
    let (program, arguments) = match action {
        "start" => ("hyperterminal-start", Vec::new()),
        "agents" => (
            "hyperterminal-catalog",
            if args.len() > 1 {
                args[1..].to_vec()
            } else {
                vec!["list".into()]
            },
        ),
        "sessions" => (
            "hyperterminal-session",
            if args.len() > 1 {
                args[1..].to_vec()
            } else {
                vec!["list".into()]
            },
        ),
        "selector" => ("hyperterminal-tab", args[1..].to_vec()),
        "clipboard" => ("hyperterminal-action", vec!["paste-image".into()]),
        _ => unreachable!(),
    };
    // Include installed compatibility helpers without discarding the user's PATH.
    let mut paths = vec![bin.clone()];
    if let Some(path) = env::var_os("PATH") {
        paths.extend(env::split_paths(&path));
    }
    let path = env::join_paths(paths).map_err(|e| e.to_string())?;
    let error = Command::new(bin.join(program))
        .args(arguments)
        .env("PATH", path)
        .exec();
    Err(format!("Cannot launch HyperTerminal: {error}"))
}
fn main() {
    match main_result() {
        Ok(code) => process::exit(code),
        Err(error) => {
            eprintln!("HyperTerminal: {error}");
            process::exit(1);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn bundle_contains_required_runtime_and_no_private_state() {
        for required in [
            "install.py",
            "README.md",
            "bin/hyperterminal-catalog",
            "bin/hyperterminal-session",
            "assets/skin/icon.svg",
        ] {
            assert!(FILES.iter().any(|(name, _)| *name == required));
        }
        assert!(FILES.iter().all(|(name, _)| !name.contains("..")
            && !std::path::Path::new(name).is_absolute()
            && !name.ends_with(".session")));
    }
}
