// AETHRIONIS Studio desktop shell.
//
// Deliberately thin. The product is served over localhost by the Python
// process; this opens a window onto it. A shell that grew its own logic would
// become a second place where the product behaves, and then two places to fix
// anything.
//
// The one thing it does beyond opening a window is make sure there is something
// to open: a packaged application whose window is blank because a separate
// process was not started is not a packaged application, it is a trap.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::io::ErrorKind;
use std::net::TcpStream;
use std::path::PathBuf;
use std::process::{Command, Stdio};
use std::thread::sleep;
use std::time::{Duration, Instant};

const ADDR: &str = "127.0.0.1:8100";

/// Is the application already answering?
fn serving() -> bool {
    TcpStream::connect_timeout(
        &ADDR.parse().expect("a literal address"),
        Duration::from_millis(300),
    )
    .is_ok()
}

/// Where the Python application lives.
///
/// Checked in order of how much the answer can be trusted: an explicit
/// environment variable, then the development checkout. A packaged build on
/// another machine has neither, and says so rather than opening a blank window.
fn application_root() -> Option<PathBuf> {
    if let Ok(root) = std::env::var("AETHRIONIS_STUDIO_ROOT") {
        let path = PathBuf::from(root);
        if path.join("studio").join("app.py").is_file() {
            return Some(path);
        }
    }
    let checkout = PathBuf::from("/home/otonom/Desktop/FH/AETHRIONIS_STUDIO");
    if checkout.join("studio").join("app.py").is_file() {
        return Some(checkout);
    }
    None
}

fn start_application() -> Result<(), String> {
    let root = application_root().ok_or_else(|| {
        "the AETHRIONIS Studio application was not found. Set          AETHRIONIS_STUDIO_ROOT to the directory containing studio/app.py."
            .to_string()
    })?;
    let python_path = format!(
        "{}:/home/otonom/Desktop/FH/DUM-E",
        root.display()
    );
    match Command::new("python3")
        .arg("-m")
        .arg("studio.app")
        .current_dir(&root)
        .env("PYTHONPATH", python_path)
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
    {
        Ok(_) => {}
        Err(error) if error.kind() == ErrorKind::NotFound => {
            return Err("python3 is not on PATH".to_string())
        }
        Err(error) => return Err(format!("could not start the application: {error}")),
    }

    // Wait for it, but not forever: a window that opens onto nothing is worse
    // than one that says what went wrong.
    let deadline = Instant::now() + Duration::from_secs(15);
    while Instant::now() < deadline {
        if serving() {
            return Ok(());
        }
        sleep(Duration::from_millis(250));
    }
    Err(format!("the application did not answer on {ADDR} within 15s"))
}

fn main() {
    if !serving() {
        if let Err(reason) = start_application() {
            eprintln!("AETHRIONIS Studio: {reason}");
        }
    }

    tauri::Builder::default()
        .run(tauri::generate_context!())
        .expect("AETHRIONIS Studio failed to start");
}
