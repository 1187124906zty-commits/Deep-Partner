use clap::{Parser, Subcommand};
use deeptutor_desktop::jobs::{JobManager, JobRequest};
use deeptutor_desktop::project_cli::{self, ProjectAction};
use deeptutor_desktop::research_cli::{self, ChatAction, WorkflowAction};
use serde_json::json;
use std::path::PathBuf;

#[derive(Parser)]
#[command(
    name = "dp",
    version,
    about = "DeepPartner projects, conversations and research workflows"
)]
struct Cli {
    #[command(subcommand)]
    command: Action,
}
#[derive(Subcommand)]
enum Action {
    /// Project-scoped conversations, durable history and stream recovery.
    Chat { #[command(subcommand)] command: ChatAction },
    /// Deterministic research tools, project records and evidence graph.
    Workflow { #[command(subcommand)] command: WorkflowAction },
    Login {
        #[arg(long)]
        username: String,
        #[arg(long, help = "Read the password from stdin, for scripts")]
        password_stdin: bool,
    },
    Logout,
    Project {
        #[command(subcommand)]
        command: ProjectAction,
    },
    Doctor {
        #[arg(long)]
        json: bool,
    },
    Task {
        #[command(subcommand)]
        command: Task,
    },
    #[command(name = "__worker", hide = true)]
    Worker {
        id: String,
        #[arg(long)]
        jobs_root: PathBuf,
    },
}
#[derive(Subcommand)]
enum Task {
    Run {
        #[arg(long)]
        engine: String,
        #[arg(long)]
        cwd: PathBuf,
        #[arg(long)]
        prompt: String,
        #[arg(long)]
        json: bool,
    },
    Status {
        id: String,
        #[arg(long)]
        json: bool,
    },
    Events {
        id: String,
        #[arg(long, default_value_t = 0)]
        after: u64,
        #[arg(long)]
        jsonl: bool,
    },
    Cancel {
        id: String,
    },
}
#[tokio::main]
async fn main() -> std::process::ExitCode {
    match run(Cli::parse()).await {
        Ok(()) => std::process::ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("{}", json!({"error":format!("{error:#}")}));
            std::process::ExitCode::FAILURE
        }
    }
}
async fn run(cli: Cli) -> anyhow::Result<()> {
    let jobs = JobManager::standard();
    match cli.command {
        Action::Chat { command } => research_cli::chat(command).await?,
        Action::Workflow { command } => research_cli::workflow(command).await?,
        Action::Login { username, password_stdin } => project_cli::login(&username, password_stdin).await?,
        Action::Logout => project_cli::logout().await?,
        Action::Project { command } => project_cli::run(command).await?,
        Action::Doctor { json: as_json } => {
            let result = json!({"version":env!("CARGO_PKG_VERSION"),"engines":JobManager::engines().await,"jobs":jobs.list(),"mode":"noninteractive","interactive_approvals":false});
            if as_json {
                println!("{result}");
            } else {
                println!("DeepPartner {}", env!("CARGO_PKG_VERSION"));
                for engine in result["engines"].as_array().unwrap() {
                    println!(
                        "{}: {}",
                        engine["id"].as_str().unwrap_or(""),
                        engine["version"].as_str().unwrap_or("unavailable")
                    );
                }
            }
        }
        Action::Task { command } => match command {
            Task::Run {
                engine,
                cwd,
                prompt,
                json: as_json,
            } => {
                let job = jobs
                    .start(JobRequest {
                        engine,
                        cwd,
                        prompt,
                        project_id: None,
                    })
                    .await?;
                if as_json {
                    println!("{}", serde_json::to_string(&job)?);
                } else {
                    println!("{} {}", job.id, job.status);
                }
            }
            Task::Status { id, json: as_json } => {
                let job = jobs.status(&id)?;
                if as_json {
                    println!("{}", serde_json::to_string(&job)?);
                } else {
                    println!("{} {} exit={:?}", job.id, job.status, job.exit_code);
                }
            }
            Task::Events { id, after, jsonl } => {
                let result = jobs.events(&id, after)?;
                if jsonl {
                    for event in result["events"].as_array().unwrap() {
                        println!("{event}");
                    }
                } else {
                    println!("{result}");
                }
            }
            Task::Cancel { id } => {
                let job = jobs.cancel(&id)?;
                println!("{}", serde_json::to_string(&job)?);
            }
        },
        Action::Worker { id, jobs_root } => JobManager::new(jobs_root).run_worker(&id).await?,
    }
    Ok(())
}
