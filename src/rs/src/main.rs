mod cli;
mod inventory;
mod lifecycle;
mod plugins;

fn main() {
    std::process::exit(cli::run(std::env::args_os().skip(1).collect()));
}
