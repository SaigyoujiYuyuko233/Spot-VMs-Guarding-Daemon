import json
import os.path
import subprocess
import time

from cleo.commands.command import Command
from cleo.helpers import option

from loguru import logger

from util import tf_state_util


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

        if not os.path.isdir(config_root):
            raise logger.critical(Exception(f"Path [{config_root}] should be a directory"))

        if not os.path.isfile(f"{config_root}/main.tf"):
            raise logger.critical(Exception(f"Terraform config [{config_root}/main.tf] does not exist"))

        # init tf
        if not self.option("skip-tf-init"):
            logger.info("Initializing Terraform")
            tf_init_cmd = subprocess.run(["tofu", "init", "-no-color"], cwd=config_root, stdout=-1)
            if tf_init_cmd.returncode != 0:
                raise logger.critical("Terraform init failed", Exception(tf_init_cmd.stdout.decode("utf-8")))
            logger.info("Terraform initialized!")
        else:
            logger.info("Skipping Terraform initialization")

        first_run = True
        while True:
            if not first_run:
                time.sleep(int(self.option("interval")))
            first_run = False

            # refresh states
            logger.info("Comparing remote resources...")
            tf_plan_cmd = subprocess.run(["tofu", "plan", "-detailed-exitcode"], cwd=config_root, stdout=-1)
            if tf_plan_cmd.returncode == 0:
                logger.info("Remote is same as local! Skipping..")

            if tf_plan_cmd.returncode == 1:
                logger.error("Terraform plan failed! Retry later...",
                             Exception(tf_plan_cmd.stdout.decode("utf-8")))
                continue

            # If there is differences, apply it
            if tf_plan_cmd.returncode == 2:
                logger.info("Remote is different from local!")
                logger.info("Applying Terraform resources...")

                tf_apply_cmd = subprocess.run(["tofu", "apply", "-no-color", "-auto-approve"], cwd=config_root, stdout=-1)
                if tf_apply_cmd.returncode != 0:
                    logger.error("Terraform apply failed! Retry later...",
                                 Exception(tf_apply_cmd.stdout.decode("utf-8")))
                    continue

            # re-check instance after applying
            try:
                tf_state_path = f"{config_root}/terraform.tfstate"
                instance = tf_state_util.find_vm_instance(self.load_json(tf_state_path)["resources"])
            except Exception as e:
                logger.error("Fail to load Terraform state after apply!", e)
                continue

            if instance is None:
                logger.error(Exception(
                    f"Can not find instance created before! How is this possible? Skipping..."))
                continue

            try:
                instance = tf_state_util.find_vm_instance(self.load_json(tf_state_path)["resources"])
            except Exception as e:
                logger.error("Fail to load Terraform state!", e)
                continue

            # For logging purpose
            if tf_plan_cmd.returncode == 2:
                # TODO: attribute might not be compatible for other provider
                logger.info(f"Instance {instance['instance_name']}[{instance['id']}] created! Instance IP: {instance['public_ip']}")
