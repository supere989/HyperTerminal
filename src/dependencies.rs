use std::{
    collections::BTreeSet,
    env, fs,
    io::{self, IsTerminal, Write},
    os::unix::fs::PermissionsExt,
    path::{Path, PathBuf},
    process::Command,
};

pub struct Dependency {
    pub name: &'static str,
    pub binaries: &'static [&'static str],
    arch: &'static str,
    debian: &'static str,
    fedora: &'static str,
}
macro_rules! dep { ($name:literal,[$($bin:literal),+],$a:literal,$d:literal,$f:literal) => {Dependency{name:$name,binaries:&[$($bin),+],arch:$a,debian:$d,fedora:$f}}; }
pub static DEPENDENCIES: &[Dependency] = &[
    dep!("Python 3", ["python3"], "python", "python3", "python3"),
    dep!("Bash", ["bash"], "bash", "bash", "bash"),
    dep!("Fish", ["fish"], "fish", "fish", "fish"),
    dep!("tmux", ["tmux"], "tmux", "tmux", "tmux"),
    dep!("fzf", ["fzf"], "fzf", "fzf", "fzf"),
    dep!("Yakuake", ["yakuake"], "yakuake", "yakuake", "yakuake"),
    dep!("Konsole", ["konsole"], "konsole", "konsole", "konsole"),
    dep!(
        "Qt 6 D-Bus",
        [
            "qdbus6",
            "qdbus-qt6",
            "/usr/bin/qdbus6",
            "/usr/bin/qdbus-qt6",
            "/usr/lib/qt6/bin/qdbus",
            "/usr/lib64/qt6/bin/qdbus"
        ],
        "qt6-tools",
        "qdbus-qt6",
        "qt6-qttools"
    ),
    dep!("ripgrep", ["rg"], "ripgrep", "ripgrep", "ripgrep"),
    dep!(
        "Wayland clipboard copy",
        ["wl-copy"],
        "wl-clipboard",
        "wl-clipboard",
        "wl-clipboard"
    ),
    dep!(
        "Wayland clipboard paste",
        ["wl-paste"],
        "wl-clipboard",
        "wl-clipboard",
        "wl-clipboard"
    ),
    dep!("flock", ["flock"], "util-linux", "util-linux", "util-linux"),
    dep!(
        "process inspection",
        ["ps"],
        "procps-ng",
        "procps",
        "procps-ng"
    ),
    dep!("awk", ["awk"], "gawk", "gawk", "gawk"),
    dep!("sed", ["sed"], "sed", "sed", "sed"),
    dep!("grep", ["grep"], "grep", "grep", "grep"),
    dep!("Base64", ["base64"], "coreutils", "coreutils", "coreutils"),
    dep!(
        "temporary files",
        ["mktemp"],
        "coreutils",
        "coreutils",
        "coreutils"
    ),
    dep!(
        "directory creation",
        ["mkdir"],
        "coreutils",
        "coreutils",
        "coreutils"
    ),
    dep!(
        "file modes",
        ["chmod"],
        "coreutils",
        "coreutils",
        "coreutils"
    ),
    dep!("file moves", ["mv"], "coreutils", "coreutils", "coreutils"),
    dep!(
        "file removal",
        ["rm"],
        "coreutils",
        "coreutils",
        "coreutils"
    ),
    dep!(
        "file unlink",
        ["unlink"],
        "coreutils",
        "coreutils",
        "coreutils"
    ),
    dep!("date", ["date"], "coreutils", "coreutils", "coreutils"),
    dep!("word count", ["wc"], "coreutils", "coreutils", "coreutils"),
    dep!(
        "text translation",
        ["tr"],
        "coreutils",
        "coreutils",
        "coreutils"
    ),
    dep!("delay", ["sleep"], "coreutils", "coreutils", "coreutils"),
    dep!(
        "service startup",
        ["true"],
        "coreutils",
        "coreutils",
        "coreutils"
    ),
];

fn executable(path: &Path) -> bool {
    path.is_file()
        && path
            .metadata()
            .map(|m| m.permissions().mode() & 0o111 != 0)
            .unwrap_or(false)
}
pub fn find_in(name: &str, search: &std::ffi::OsStr) -> Option<PathBuf> {
    if name.contains('/') {
        let path = PathBuf::from(name);
        return executable(&path).then_some(path);
    }
    env::split_paths(search)
        .map(|dir| dir.join(name))
        .find(|path| executable(path))
}
pub fn find(name: &str) -> Option<PathBuf> {
    find_in(name, &env::var_os("PATH").unwrap_or_default())
}
fn found(dep: &Dependency) -> Option<PathBuf> {
    for name in dep.binaries {
        if let Some(path) = find(name) {
            // Our compatibility shim is not evidence that the underlying Qt tool exists.
            if dep.name == "Qt 6 D-Bus"
                && fs::read(&path).ok().is_some_and(|bytes| {
                    bytes.len() < 4096
                        && String::from_utf8_lossy(&bytes).contains("HyperTerminal: Qt 6 qdbus")
                })
            {
                continue;
            }
            return Some(path);
        }
    }
    None
}
pub fn missing() -> Vec<&'static Dependency> {
    DEPENDENCIES
        .iter()
        .filter(|dep| found(dep).is_none())
        .collect()
}
pub fn doctor() -> bool {
    println!("HyperTerminal dependency check:");
    let mut okay = true;
    for dep in DEPENDENCIES {
        if let Some(path) = found(dep) {
            println!("  OK       {:<24} {}", dep.name, path.display());
        } else {
            println!("  MISSING  {}", dep.name);
            okay = false;
        }
    }
    println!("Coding agents are detected separately; they are never automatically installed.");
    okay
}

#[derive(Debug, PartialEq, Eq, Clone, Copy)]
pub enum Distro {
    Arch,
    Debian,
    Fedora,
}
pub fn distro_from(text: &str) -> Option<Distro> {
    let mut tokens = Vec::new();
    for line in text.lines() {
        if let Some((key, value)) = line.split_once('=') {
            if key == "ID" || key == "ID_LIKE" {
                tokens.extend(
                    value
                        .trim_matches(['"', '\''])
                        .split_whitespace()
                        .map(str::to_owned),
                );
            }
        }
    }
    if tokens.iter().any(|t| t == "arch") {
        Some(Distro::Arch)
    } else if tokens.iter().any(|t| t == "debian" || t == "ubuntu") {
        Some(Distro::Debian)
    } else if tokens.iter().any(|t| t == "fedora") {
        Some(Distro::Fedora)
    } else {
        None
    }
}
pub fn plan(distro: Distro, missing: &[&Dependency]) -> (String, Vec<String>) {
    let packages: BTreeSet<_> = missing
        .iter()
        .map(|dep| match distro {
            Distro::Arch => dep.arch,
            Distro::Debian => dep.debian,
            Distro::Fedora => dep.fedora,
        })
        .collect();
    let (program, flags) = match distro {
        Distro::Arch => ("pacman", vec!["-S", "--needed", "--noconfirm", "--"]),
        Distro::Debian => ("apt-get", vec!["install", "--yes", "--"]),
        Distro::Fedora => ("dnf", vec!["install", "--assumeyes", "--"]),
    };
    let mut args: Vec<String> = flags.into_iter().map(str::to_owned).collect();
    args.extend(packages.into_iter().map(str::to_owned));
    (program.to_owned(), args)
}
pub fn affirmative(answer: &str) -> bool {
    matches!(answer.trim().to_ascii_lowercase().as_str(), "y" | "yes")
}
pub fn confirm(message: &str) -> Result<bool, String> {
    if io::stdin().is_terminal() && io::stdout().is_terminal() {
        print!("{message}\nProceed? [y/N] ");
        io::stdout().flush().map_err(|e| e.to_string())?;
        let mut answer = String::new();
        io::stdin()
            .read_line(&mut answer)
            .map_err(|e| e.to_string())?;
        return Ok(affirmative(&answer));
    }
    if let Some(dialog) = find("kdialog") {
        // A radio list explicitly selects No by default on every supported KDialog.
        let output = Command::new(dialog)
            .args([
                "--title",
                "HyperTerminal",
                "--radiolist",
                message,
                "decline",
                "No — cancel",
                "on",
                "approve",
                "Yes — proceed",
                "off",
            ])
            .output()
            .map_err(|e| e.to_string())?;
        return Ok(
            output.status.success() && String::from_utf8_lossy(&output.stdout).trim() == "approve"
        );
    }
    Err("No interactive terminal or kdialog is available. Run HyperTerminal in a terminal to review and approve setup. No installation was performed.".into())
}
pub fn ensure() -> Result<(), String> {
    let absent = missing();
    if absent.is_empty() {
        return Ok(());
    }
    let names = absent
        .iter()
        .map(|dep| dep.name)
        .collect::<Vec<_>>()
        .join(", ");
    let distro=distro_from(&fs::read_to_string("/etc/os-release").map_err(|e|e.to_string())?).ok_or_else(||format!("Missing dependencies: {names}. Automatic installation supports Arch/Garuda, Debian/Ubuntu, and Fedora. Install these manually on this distribution."))?;
    let (program, args) = plan(distro, &absent);
    let package_manager=find(&program).ok_or_else(||format!("Package manager {program} is unavailable. Install missing dependencies manually: {names}"))?;
    let interactive = io::stdin().is_terminal();
    let elevation = find(if interactive { "sudo" } else { "pkexec" }).ok_or_else(|| {
        format!(
            "{} is required to authorize system package installation. Missing: {names}",
            if interactive { "sudo" } else { "pkexec" }
        )
    })?;
    let message=format!("HyperTerminal requires: {names}\n\nDownload and install these packages using your configured distribution repositories:\n\n{} {} {}\n\nThis changes system packages and requires administrator authentication. HyperTerminal session records and agent credentials are not included.",elevation.display(),package_manager.display(),args.join(" "));
    if !confirm(&message)? {
        return Err("Dependency installation declined. No packages were installed.".into());
    }
    let status = Command::new(elevation)
        .arg(package_manager)
        .args(args)
        .status()
        .map_err(|e| format!("Cannot start package installation: {e}"))?;
    if !status.success() {
        return Err(format!("Package installation failed ({status}); HyperTerminal setup was not deployed. You can retry."));
    }
    let remaining = missing();
    if !remaining.is_empty() {
        return Err(format!(
            "Installation completed, but these dependencies are still unavailable: {}",
            remaining
                .iter()
                .map(|dep| dep.name)
                .collect::<Vec<_>>()
                .join(", ")
        ));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn consent_is_explicit() {
        for answer in ["", "n", "no", "maybe", "true"] {
            assert!(!affirmative(answer));
        }
        for answer in ["y", "YES", " Yes\n"] {
            assert!(affirmative(answer));
        }
    }
    #[test]
    fn distro_uses_id_and_family() {
        assert_eq!(distro_from("ID=garuda\nID_LIKE=arch"), Some(Distro::Arch));
        assert_eq!(
            distro_from("ID=ubuntu\nID_LIKE=debian"),
            Some(Distro::Debian)
        );
        assert_eq!(
            distro_from("ID=nobara\nID_LIKE=\"fedora\""),
            Some(Distro::Fedora)
        );
        assert_eq!(distro_from("ID=unknown"), None);
    }
    #[test]
    fn plans_deduplicate_packages_and_use_args() {
        let subset = vec![&DEPENDENCIES[9], &DEPENDENCIES[10]];
        for distro in [Distro::Arch, Distro::Debian, Distro::Fedora] {
            let (_, args) = plan(distro, &subset);
            assert_eq!(
                args.iter()
                    .filter(|arg| arg.as_str() == "wl-clipboard")
                    .count(),
                1
            );
            assert!(args.contains(&"--".into()));
        }
        let (_, debian) = plan(Distro::Debian, &[&DEPENDENCIES[7]]);
        assert!(debian.contains(&"qdbus-qt6".into()));
    }
    #[test]
    fn executable_check_rejects_nonexecutable_file() {
        let root = env::temp_dir().join(format!("ht-dep-test-{}", std::process::id()));
        fs::create_dir_all(&root).unwrap();
        let file = root.join("fixture");
        fs::write(&file, b"#!/bin/sh\n").unwrap();
        fs::set_permissions(&file, fs::Permissions::from_mode(0o600)).unwrap();
        assert!(find_in("fixture", root.as_os_str()).is_none());
        fs::set_permissions(&file, fs::Permissions::from_mode(0o700)).unwrap();
        assert!(find_in("fixture", root.as_os_str()).is_some());
        fs::remove_dir_all(root).unwrap();
    }
}
