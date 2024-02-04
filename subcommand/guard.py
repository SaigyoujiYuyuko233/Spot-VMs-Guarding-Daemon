import json
import os.path
import subprocess
import time

from cleo.commands.command import Command
from cleo.helpers import option

from loguru import logger


class GuardCommand(Command):
    name = "guard"
    description = "Guard vm specified by config"
    options = [
        option(
            "config",
            "c",
            description="Config path that include both terraform and ansible",
            flag=False,
            value_required=True,
        ),
        option(
            "interval",
            "i",
            description="Check vm state every N seconds",
            flag=False,
            value_required=True,
            default=30
        ),
        option(
            "skip-tf-init",
            description="Skip terraform init",
            flag=True,
        )
    ]

    @staticmethod
    def load_json(path):
        payload = None
        with open(path, 'r', encoding="utf-8") as f:
            payload = json.load(f)
            f.close()
        return payload

    def handle(self):
        config_root = self.option("config")
        tf_path = f"{config_root}/terraform"

        if not os.path.isdir(config_root):
            raise logger.critical(Exception(f"Path [{config_root}] should be a directory"))

        if not os.path.isfile(f"{tf_path}/main.tf"):
            raise logger.critical(Exception(f"Terraform config [{tf_path}/main.tf] does not exist"))

        # init tf
        if not self.option("skip-tf-init"):
            logger.info("Initializing Terraform")
            tf_init_cmd = subprocess.run(["tofu", "init", "-no-color"], cwd=tf_path, stdout=-1)
            if tf_init_cmd.returncode != 0:
                raise logger.critical("Terraform init failed", Exception(tf_init_cmd.stdout.decode("utf-8")))
            logger.info("Terraform initialized!")
        else:
            logger.info("Skipping Terraform initialization")

        first_run = True
        ansible_ran = True
        while True:
            if not first_run:
                time.sleep(int(self.option("interval")))
            first_run = False

            # refresh states
            logger.info("Refreshing state...")
            tf_refresh_cmd = subprocess.run(["tofu", "refresh", "-no-color"], cwd=tf_path, stdout=-1)
            if tf_refresh_cmd.returncode != 0:
                logger.error("Terraform refresh failed! Retry later...",
                             Exception(tf_refresh_cmd.stdout.decode("utf-8")))
                continue
            logger.info("Terraform state refreshed")

            # check resources
            tf_state_path = f"{tf_path}/terraform.tfstate"
            if not os.path.isfile(tf_state_path):
                logger.error(Exception(
                    f"Terraform state file [{tf_state_path}] does not exist! How is this possible? Skipping..."))
                continue

            try:
                tf_state = self.load_json(tf_state_path)["resources"]
            except Exception as e:
                logger.error("Fail to load Terraform state!", e)
                continue

            # create instance
            if len(tf_state) < 0:
                logger.info("Creating instance...")
                tf_apply_cmd = subprocess.run(["tofu", "apply", "-no-color", "-auto-approve"], cwd=tf_path, stdout=-1)
                if tf_apply_cmd.returncode != 0:
                    logger.error("Terraform apply failed! Retry later...", Exception(tf_apply_cmd.stdout.decode("utf-8")))
                    continue
                ansible_ran = False
            else:
                # TODO: Change default index 0 to func that auto find instance index
                logger.info(f"Instance [{tf_state[0]['name']}] exists. Skip creating...")

            try:
                # TODO: Change default index 0 to func that auto find instance index
                instance = self.load_json(tf_state_path)["resources"][0]
            except Exception as e:
                logger.error("Fail to load Terraform state!", e)
                continue

            if len(tf_state) < 0:
                logger.info(f"Instance [{instance['id']}] created! IP: {instance['public_ip']}")

            # Run ansible
            if ansible_ran:
                logger.info(f"No need for running ansible [{tf_state[0]['name']}]. Skip...")
                continue

            # TODO: Run ansible
            ansible_ran = True
