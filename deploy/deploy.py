"""Put Meal Planner on a free Google Cloud VM, and keep it updated. Run from this repo on Windows.

  python deploy/deploy.py create      make the VM, set it up, copy your data, set the site password
  python deploy/deploy.py update      after pushing new code: pull it on the server and restart
  python deploy/deploy.py password    set a new site password
  python deploy/deploy.py backup      download the server's data into backups/
  python deploy/deploy.py push-data   replace the server's data with your local instance/ folder

Needs: gcloud logged in (gcloud auth login) and a project with billing on (gcloud config set project ...).
The VM is an e2-micro in us-west1, which is inside Google's Always Free tier.
"""
import getpass
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

NAME = "mealplanner"
ZONE = "us-west1-b"
ROOT = Path(__file__).resolve().parent.parent
GCLOUD = shutil.which("gcloud") or shutil.which("gcloud.cmd") or "gcloud"


def gc(*args, capture=False, check=True):
    cmd = [GCLOUD, *args]
    print("> gcloud " + " ".join(args))
    r = subprocess.run(cmd, capture_output=capture, text=True, shell=False)
    if check and r.returncode != 0:
        sys.exit(f"gcloud failed: {(r.stderr or '').strip()[-400:]}")
    return r.stdout.strip() if capture else r


def ssh(command):
    return gc("compute", "ssh", NAME, "--zone", ZONE, "--quiet", "--command", command)


def external_ip():
    return gc("compute", "instances", "describe", NAME, "--zone", ZONE,
              "--format=value(networkInterfaces[0].accessConfigs[0].natIP)", capture=True)


def domain(ip):
    return ip.replace(".", "-") + ".sslip.io"


def set_password(pw=None):
    from werkzeug.security import generate_password_hash
    pw = pw or getpass.getpass("New site password (8+ characters): ")
    if len(pw) < 8:
        sys.exit("Use at least 8 characters.")
    h = generate_password_hash(pw)
    ssh(f"sudo sed -i '/^MEALPLANNER_SITE_PASSWORD_HASH=/d' /etc/mealplanner.env && "
        f"echo 'MEALPLANNER_SITE_PASSWORD_HASH={h}' | sudo tee -a /etc/mealplanner.env >/dev/null && "
        f"sudo systemctl restart mealplanner")
    return pw


def push_data():
    inst = ROOT / "instance"
    if not inst.exists():
        print("No local instance/ folder, starting empty.")
        return
    with tempfile.TemporaryDirectory() as tmp:
        arch = shutil.make_archive(str(Path(tmp) / "instance"), "gztar", inst)
        gc("compute", "scp", "--zone", ZONE, "--quiet", arch, f"{NAME}:/tmp/instance.tar.gz")
    ssh("sudo systemctl stop mealplanner && sudo rm -rf /opt/mealplanner/instance.old && "
        "sudo mv /opt/mealplanner/instance /opt/mealplanner/instance.old && sudo mkdir /opt/mealplanner/instance && "
        "sudo tar -xzf /tmp/instance.tar.gz -C /opt/mealplanner/instance && rm /tmp/instance.tar.gz && "
        "sudo chown -R mealplanner:mealplanner /opt/mealplanner/instance && sudo systemctl start mealplanner")


def create():
    existing = gc("compute", "instances", "list", f"--filter=name={NAME}", "--format=value(name)", capture=True)
    if not existing:
        gc("services", "enable", "compute.googleapis.com")
        gc("compute", "instances", "create", NAME, "--zone", ZONE, "--machine-type", "e2-micro",
           "--image-family", "debian-12", "--image-project", "debian-cloud",
           "--boot-disk-size", "30GB", "--boot-disk-type", "pd-standard", "--tags", "http-server,https-server")
        rules = gc("compute", "firewall-rules", "list", "--format=value(name)", capture=True).split()
        for name, port in (("allow-http-mealplanner", "80"), ("allow-https-mealplanner", "443")):
            if name not in rules:
                gc("compute", "firewall-rules", "create", name, "--allow", f"tcp:{port}",
                   "--target-tags", "http-server,https-server")
        print("Waiting for the VM to boot...")
        time.sleep(40)
    ip = external_ip()
    dom = domain(ip)
    gc("compute", "scp", "--zone", ZONE, "--quiet", str(ROOT / "deploy" / "server_setup.sh"), f"{NAME}:/tmp/server_setup.sh")
    ssh(f"sudo bash /tmp/server_setup.sh {dom}")
    push_data()
    pw = set_password(secrets.token_urlsafe(9))
    print(f"\nLive: https://{dom}\nSite password: {pw}\n(change it any time: python deploy/deploy.py password)")


def update():
    ssh("sudo -u mealplanner git -C /opt/mealplanner pull -q --ff-only && "
        "sudo /opt/mealplanner/.venv/bin/pip install -q -r /opt/mealplanner/requirements.txt waitress && "
        "sudo systemctl restart mealplanner && systemctl is-active mealplanner")
    print(f"Updated: https://{domain(external_ip())}")


def backup():
    out = ROOT / "backups"
    out.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    ssh("sudo tar -czf /tmp/mp-backup.tar.gz -C /opt/mealplanner instance && sudo chmod 644 /tmp/mp-backup.tar.gz")
    gc("compute", "scp", "--zone", ZONE, "--quiet", f"{NAME}:/tmp/mp-backup.tar.gz", str(out / f"mealplanner-{stamp}.tar.gz"))
    print(f"Saved backups/mealplanner-{stamp}.tar.gz")


if __name__ == "__main__":
    actions = {"create": create, "update": update, "password": lambda: set_password(), "backup": backup,
               "push-data": push_data}
    if len(sys.argv) != 2 or sys.argv[1] not in actions:
        sys.exit(__doc__)
    actions[sys.argv[1]]()
