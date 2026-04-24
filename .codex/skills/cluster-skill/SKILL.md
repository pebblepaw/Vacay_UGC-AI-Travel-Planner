---
name: cluster-skill
description: Access and use the NUS SoC Slurm compute cluster for running jobs, transferring files, and managing Python environments. Use when the user needs to run code on the cluster, submit batch jobs, monitor output, install packages, or transfer files between local and remote.
---

# SoC Cluster Usage

## Connection

The cluster login node is `xlogin0.comp.nus.edu.sg`. The SSH config alias is `soc-cluster`.

```bash
ssh soc-cluster
```

The user's SSH config should have an entry like this in `~/.ssh/config`:

```sshconfig
Host soc-cluster
    HostName xlogin0.comp.nus.edu.sg
    User <soc_username>
    IdentityFile ~/.ssh/id_ed25519
    ForwardAgent yes
    ForwardX11 no
```

If the user hasn't set up SSH keys, generate them first:

```bash
ssh-keygen -t ed25519 -C "nusnet_email@nus.edu.sg"
ssh-copy-id soc-cluster
```

## Important: Do not run work on the login node

The SoC login node (`xlogin`) has strict process limits. All computation, including VSCode/Cursor tunnel connections, must happen on compute nodes. Request a compute node before doing anything.

## Requesting compute nodes

**CPU interactive session:**

```bash
salloc --nodes=1 --ntasks=1 --time=1:00:00
srun --pty bash
```

The prompt should change from `xlogin` to `cnc` (compute node). Adjust `--time` as needed. CPU partition has a 1-day time limit.

**GPU interactive session:**

```bash
salloc --partition=gpu --gres=gpu:h100-47:2
```

GPU partition has a 3-day time limit. Available GPU types:
- `gpu:h100-47:<N>` — H100 with 47GB VRAM
- `gpu:h100-96:<N>` — H100 with 96GB VRAM
- `gpu:a100-40:<N>` — A100 with 40GB VRAM
- `gpu:v100:<N>` — V100

Check current GPU availability with `sinfo -p gpu`.

**Always release sessions when done.** Idle interactive sessions may be terminated by admins.

## VSCode / Cursor tunnel on compute nodes

Install the CLI once on the compute node:

```bash
# VSCode
curl -Lk 'https://code.visualstudio.com/sha/download?build=stable&os=cli-alpine-x64' --output vscode_cli.tar.gz
tar -xf vscode_cli.tar.gz

# Or Cursor
curl -Lk 'https://api2.cursor.sh/updates/download-latest?os=cli-alpine-x64' --output cursor_cli.tar.gz
tar -xf cursor_cli.tar.gz
```

Start the tunnel from a compute node (not the login node):

```bash
./code tunnel   # or ./cursor tunnel
```

Authenticate via GitHub when prompted. Then in your local VSCode, click the bottom-left remote icon, select "Tunnel", and connect.

## Submitting batch jobs

Batch jobs are the standard way to run work. Write a batch script:

```bash
#!/bin/bash
#SBATCH --job-name=my_job
#SBATCH --output=run_%j.out
#SBATCH --error=run_%j.err
#SBATCH --partition=gpu          # or omit for CPU partition
#SBATCH --gres=gpu:1             # only for GPU jobs
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=03:00:00

python3 -u my_script.py
```

Submit from the login node:

```bash
sbatch my_job.sh
```

Key SBATCH options:
- `--job-name`: name shown in the queue
- `--output=run_%j.out`: stdout file (`%j` is replaced by job ID)
- `--error=run_%j.err`: stderr file
- `--partition`: `gpu` for GPU jobs, omit or use default for CPU
- `--gres=gpu:<type>:<count>`: GPU type and quantity
- `--ntasks`: number of processes
- `--cpus-per-task`: CPU cores per process
- `--mem`: total memory
- `--time`: wall-clock time limit (HH:MM:SS)

Always use `python3 -u` (unbuffered output) so you can tail the output file in real time.

## Monitoring jobs

```bash
# See all your jobs
squeue -u $USER

# See detailed status of a specific job
sacct -j <jobid> --format=JobID,State,ExitCode,Elapsed

# Watch output in real time (while job is running)
tail -f run_<jobid>.out

# Check why a job failed
sacct -j <jobid> --format=JobID,State,ExitCode
cat run_<jobid>.err

# Cancel a job
scancel <jobid>
```

## Transferring files

**Local to cluster:**

```bash
scp local_file.py soc-cluster:~/Assignment_2/
scp -r local_folder/ soc-cluster:~/Assignment_2/
```

**Cluster to local:**

```bash
scp soc-cluster:~/Assignment_2/output.csv ./
scp soc-cluster:~/Assignment_2/run_12345.out ./
```

**For many files or large transfers, use rsync:**

```bash
# Sync local directory to cluster (only changed files)
rsync -avz --progress ./project/ soc-cluster:~/Assignment_2/

# Sync cluster results back to local
rsync -avz --progress soc-cluster:~/Assignment_2/run_*.out ./results/
```

**Best practices for file transfer:**
- Use `rsync` over `scp` when syncing directories — it only transfers changed files.
- Transfer from the login node, not compute nodes.
- Don't transfer large datasets repeatedly. Upload once, keep on cluster.
- Use `--exclude` with rsync to skip files you don't need (e.g. `--exclude='__pycache__'`).
- If the cluster internet connection is poor, do **not** download large datasets, model weights, or archives directly on the cluster. Download them on your local machine first, optionally zip/archive them locally, then upload them with `scp` or `rsync`.
- For very large assets, prefer the workflow: `download on laptop -> verify locally -> archive if helpful -> scp to soc-cluster -> unpack on cluster`.

## Installing Python packages

The cluster has a system Python. Install packages to your user directory:

```bash
pip3 install --user scikit-learn pandas numpy scipy nltk afinn
```

Packages go to `~/.local/lib/python3.x/site-packages/`. This persists across sessions.

**To check what's installed:**

```bash
pip3 list --user
python3 -c "import sklearn; print(sklearn.__version__)"
```

**NLTK data** needs to be downloaded separately:

```bash
python3 -c "import nltk; nltk.download('punkt'); nltk.download('wordnet'); nltk.download('stopwords'); nltk.download('sentiwordnet'); nltk.download('averaged_perceptron_tagger'); nltk.download('opinion_lexicon')"
```

**If a package isn't available via pip** (e.g. needs compilation or system libraries), check if there's a module for it:

```bash
module avail
module load cuda    # example: load CUDA
module load rapids  # example: load RAPIDS for GPU-accelerated sklearn
```

## Using tmux for persistent sessions

Always use tmux on the login node so your session survives disconnects:

```bash
# Start a new session
tmux new -s mywork

# Detach: Ctrl+B then D

# Reattach after reconnecting
tmux attach -t mywork

# List sessions
tmux ls
```

This is especially important when monitoring long-running jobs or keeping a tunnel alive.

## Typical workflow

1. **SSH in:** `ssh soc-cluster`
2. **Start tmux:** `tmux new -s work` (or reattach with `tmux attach -t work`)
3. **Transfer files:** `scp` or `rsync` your code to the cluster. For large datasets/models, download them locally first, then upload them; avoid large direct cluster downloads when the cluster internet is unreliable.
4. **Install dependencies** (first time): `pip3 install --user <packages>`
5. **Write a batch script** with appropriate resources
6. **Submit:** `sbatch my_job.sh`
7. **Monitor:** `squeue -u $USER` and `tail -f run_<jobid>.out`
8. **Retrieve results:** `scp soc-cluster:~/path/to/output.csv ./`

## Slurm quick reference

| Action | Command |
|--------|---------|
| Submit a batch job | `sbatch script.sh` |
| Check your jobs | `squeue -u $USER` |
| Cancel a job | `scancel <jobid>` |
| Job exit status | `sacct -j <jobid> --format=JobID,State,ExitCode` |
| Available GPUs | `sinfo -p gpu` |
| Partition info | `sinfo --format="%P %G %D %C"` |
| Run on specific node | `srun --nodelist=<node> <command>` |
| Interactive CPU | `salloc --nodes=1 --ntasks=1 --time=1:00:00` then `srun --pty bash` |
| Interactive GPU | `salloc --partition=gpu --gres=gpu:h100-47:1` |

## Resource allocation parameters

- `--ntasks`: total number of processes to launch
- `--nodes`: number of nodes to spread tasks across
- `--tasks-per-node`: maximum tasks per node
- `--cpus-per-task`: CPU cores per task
- `--gpus-per-task`: GPUs per task (for GPU jobs)
- Total CPU cores used = `ntasks` × `cpus-per-task`

## Partition time limits

- **CPU partition:** 1-day maximum
- **GPU partition:** 3-day maximum

Plan your job's `--time` accordingly. If your job needs less than 1 hour, use a shorter time limit — shorter jobs get scheduled faster.
