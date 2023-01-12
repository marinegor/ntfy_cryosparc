# CryoSPARC 

Very simple HTTP server in pure python for processing local cryosparc notifications and posting them to a ntfy.sh channel.

## Installation

1. Set the variable `CRYOSPARC_SLACK_WEBHOOK_URL` in your `config.sh (see [cryosparc documentation](https://guide.cryosparc.com/setup-configuration-and-management/management-and-monitoring/environment-variables#cryosparc_master-config.sh) and [my thread](https://discuss.cryosparc.com/t/push-notifications-for-long-jobs/9827/2) on discuss forum). Note that you must restart your cryosparc instance after that.
2. Login as `cryosparcuser` on your master node
3. Clone the repo and start the script:

```bash
git clone https://github.com/marinegor/ntfy_cryosparc.git
cd ntfy_cryosparc.git
cryosparcm call python3 server.py
```

## Usage

Usage:

```bash
usage: cryosparcm call python3 server.py [-h] [--url URL] [--admin ADMIN] [--hostname HOSTNAME]

optional arguments:
  -h, --help           show this help message and exit
  --url URL            location of ntfy server (change from default if you're
                       self-hosting it (default: https://ntfy.sh)
  --admin ADMIN        username for admin messages (like when a notification
                       is failed to get parsed) (default: admin)
  --hostname HOSTNAME  master node hostname, is used in notification channel
                       name: <url>/cs_<hostname>_<username> (default: cmm-1)
```

You can check if the notifications are actually sent via interrupting a `server.py` with Ctrl+C -- it sends a test notification to the admin channel before finishing the process.
