use std::{
    env, fs,
    path::{Path, PathBuf},
};
fn collect(root: &Path, path: &Path, entries: &mut Vec<PathBuf>) {
    if path.is_dir() {
        let mut children: Vec<_> = fs::read_dir(path)
            .unwrap()
            .map(|e| e.unwrap().path())
            .collect();
        children.sort();
        for child in children {
            collect(root, &child, entries);
        }
    } else {
        entries.push(path.strip_prefix(root).unwrap().to_path_buf());
    }
}
fn main() {
    let root = PathBuf::from(env::var("CARGO_MANIFEST_DIR").unwrap());
    let mut entries = Vec::new();
    for path in [
        "bin",
        "assets",
        "config",
        "desktop",
        "systemd",
        "install.py",
        "restore-install.py",
        "README.md",
        "LICENSE",
        "NOTICE.md",
    ] {
        collect(&root, &root.join(path), &mut entries);
        println!("cargo:rerun-if-changed={path}");
    }
    let mut source = String::from("pub static FILES: &[(&str, &[u8])] = &[\n");
    let mut hash = 0xcbf29ce484222325u64;
    for path in entries {
        let name = path.to_str().unwrap();
        let bytes = fs::read(root.join(&path)).unwrap();
        for byte in name.bytes().chain(bytes) {
            hash = (hash ^ u64::from(byte)).wrapping_mul(0x100000001b3);
        }
        source.push_str(&format!(
            "({name:?}, include_bytes!({:?})),\n",
            root.join(&path)
        ));
    }
    source.push_str(&format!(
        "];\npub const BUNDLE_ID: &str = \"{hash:016x}\";\n"
    ));
    fs::write(
        PathBuf::from(env::var("OUT_DIR").unwrap()).join("bundle.rs"),
        source,
    )
    .unwrap();
}
