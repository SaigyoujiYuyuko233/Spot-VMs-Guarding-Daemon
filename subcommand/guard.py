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
            "ansible-playbook",
            "p",
            description="specify ansible playbook file in user_config/ansible/",
            flag=False,
            value_required=True,
            default="playbook.yaml"
        ),
        option(
            "ansible-inventory",
            description="specify ansible inventory template file in user_config/ansible/",
            flag=False,
            value_required=True,
            default="user-inventory.ini"
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
        ansible_path = f"{config_root}/ansible"
        ansible_inv = f"{ansible_path}/{self.option('ansible-inventory')}"
        ansible_playbook = f"{ansible_path}/{self.option('ansible-playbook')}"

        if not os.path.isdir(config_root):
            raise logger.critical(Exception(f"Path [{config_root}] should be a directory"))

        if not os.path.isfile(f"{tf_path}/main.tf"):
            raise logger.critical(Exception(f"Terraform config [{tf_path}/main.tf] does not exist"))

        if not os.path.isfile(ansible_inv):
            raise logger.critical(Exception(f"Ansible inventory [{ansible_inv}] does not exist"))

        if not os.path.isfile(ansible_playbook):
            raise logger.critical(Exception(f"Ansible playbook [{ansible_playbook}] does not exist"))

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
        while True:
            if not first_run:
                time.sleep(int(self.option("interval")))
            first_run = False

            # refresh states
            logger.info("Comparing remote resources...")
            tf_refresh_cmd = subprocess.run(["tofu", "plan", "-detailed-exitcode"], cwd=tf_path, stdout=-1)
            if tf_refresh_cmd.returncode == 0:
                logger.info("Remote is same as local! Skipping..")

            if tf_refresh_cmd.returncode == 1:
                logger.error("Terraform plan failed! Retry later...",
                             Exception(tf_refresh_cmd.stdout.decode("utf-8")))
                continue

            # check resources
            tf_state_path = f"{tf_path}/terraform.tfstate"
            if not os.path.isfile(tf_state_path):
                logger.error(Exception(
                    f"Terraform state file [{tf_state_path}] does not exist! How is this possible? Skipping..."))
                continue

            # check instance here, this way we can know to run ansible or not
            try:
                instance = tf_state_util.find_vm_instance(self.load_json(tf_state_path)["resources"])
            except Exception as e:
                logger.error("Fail to load Terraform state!", e)
                continue

            # if instance does not exist, we will run ansible
            run_ansible = instance is None

            # If there is differences, apply it
            if tf_refresh_cmd.returncode == 2:
                logger.info("Remote is different from local!")
                logger.info("Applying Terraform resources...")

                tf_apply_cmd = subprocess.run(["tofu", "apply", "-no-color", "-auto-approve"], cwd=tf_path, stdout=-1)
                if tf_apply_cmd.returncode != 0:
                    logger.error("Terraform apply failed! Retry later...",
                                 Exception(tf_apply_cmd.stdout.decode("utf-8")))
                    continue

            # re-check instance after applying
            try:
                instance = tf_state_util.find_vm_instance(self.load_json(tf_state_path)["resources"])
            except Exception as e:
                logger.error("Fail to load Terraform state after apply!", e)
                continue

            if instance is None:
                logger.error(Exception(
                    f"Can not find instance created before! How is this possible? Skipping..."))
                continue

            # for logging purpose
            if tf_refresh_cmd.returncode == 2:
                # TODO: attribute might not be compatible for other provider
                logger.info(f"Instance {instance['instance_name']}[{instance['id']}] exists. Skip creating...")

            try:
                instance = tf_state_util.find_vm_instance(self.load_json(tf_state_path)["resources"])
            except Exception as e:
                logger.error("Fail to load Terraform state!", e)
                continue

            # For logging purpose
            if tf_refresh_cmd.returncode == 2:
                # TODO: attribute might not be compatible for other provider
                logger.info(f"Instance {instance['instance_name']}[{instance['id']}] created! Instance IP: {instance['public_ip']}")

            # Run ansible
            if run_ansible:
                # TODO: attribute might not be compatible for other provider
                logger.info(f"No need to run ansible on {instance['instance_name']}[{instance['id']}]. Skip...")
                continue

            # TODO: Run ansible
            if not run_ansible:
                logger.info(f"Skip ansible run on {instance['instance_name']}")
