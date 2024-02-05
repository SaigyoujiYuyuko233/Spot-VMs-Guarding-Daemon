import json
import os.path
import subprocess
import time

from cleo.commands.command import Command
from cleo.helpers import option
from loguru import logger

from util import tf_state_util, log


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
            "run-ansible",
            description="Make ansible run at first even instance is existed. Use for error recovery",
            flag=True,
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
            "ansible-extra-arg",
            description="User defined args for ansible. Such as disable host key checking",
            flag=False,
            value_required=True,
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
            log.log_critical_and_raise(Exception(f"Path [{config_root}] should be a directory"))

        if not os.path.isfile(f"{tf_path}/main.tf"):
            log.log_critical_and_raise(Exception(f"Terraform config [{tf_path}/main.tf] does not exist"))

        if not os.path.isfile(ansible_inv):
            log.log_critical_and_raise(Exception(f"Ansible inventory [{ansible_inv}] does not exist"))

        if not os.path.isfile(ansible_playbook):
            log.log_critical_and_raise(Exception(f"Ansible playbook [{ansible_playbook}] does not exist"))

        # init tf
        if not self.option("skip-tf-init"):
            logger.info("Initializing Terraform")
            tf_init_cmd = subprocess.run(["tofu", "init", "-no-color"], cwd=tf_path, stdout=-1)
            if tf_init_cmd.returncode != 0:
                log.log_critical_and_raise(Exception(f"Terraform init failed: {tf_init_cmd.stdout.decode('utf-8')}"))
            logger.info("Terraform initialized!")
        else:
            logger.info("Skipping Terraform initialization")

        first_run = True
        run_ansible = self.option("run-ansible")
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
            # if the instance is new created
            # or the previous ansible run failed
            run_ansible = instance is None or run_ansible

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
            # TODO: attribute might not be compatible for other provider
            if tf_refresh_cmd.returncode == 2:
                if instance is not None:
                    logger.info(f"Instance {instance['instance_name']}[{instance['id']}] exists. Skip creating...")
                else:
                    logger.info(f"Instance {instance['instance_name']}[{instance['id']}] created! Instance IP: {instance['public_ip']}")

            try:
                instance = tf_state_util.find_vm_instance(self.load_json(tf_state_path)["resources"])
            except Exception as e:
                logger.error("Fail to load Terraform state!", e)
                continue

            # Check ansible
            if not run_ansible:
                logger.info(f"No need to run ansible on {instance['instance_name']}[{instance['id']}]. Skip...")
                continue

            # ============ Prepare Ansible Run ============
            logger.info("Preparing Ansible run...")

            # generate inventory
            try:
                with open(ansible_inv, mode='r', encoding="utf-8") as f:
                    inv_tmp = f.read()
                    f.close()
            except Exception as e:
                logger.error("Fail to read Ansible inventory! Retry later...", e)
                continue

            inv_tmp = inv_tmp.replace("%instance_ip%", instance['public_ip'])

            try:
                ansible_inv_tmp_file = f"{ansible_path}/inventory-gen.ini"
                with open(ansible_inv_tmp_file, mode='w+', encoding="utf-8") as f:
                    f.write(inv_tmp)
                    f.close()
            except Exception as e:
                logger.error("Fail to write temperate Ansible inventory! Retry later...", e)
                continue

            # Run ansible
            ansible_playbook_cmd_args = [
                "ansible-playbook",
                "-i", "inventory-gen.ini",
                self.option('ansible-playbook')
            ]
            if self.option("ansible-extra-arg"):
                ansible_playbook_cmd_args += self.option("ansible-extra-arg").split(" ")
            logger.info("Running Ansible playbook with following arguments:")
            logger.info(ansible_playbook_cmd_args)

            ansible_playbook_cmd = subprocess.Popen(ansible_playbook_cmd_args, cwd=ansible_path, stdout=subprocess.PIPE)
            while ansible_playbook_cmd.stdout is not None:
                line = ansible_playbook_cmd.stdout.readline().decode("utf-8")
                if not line:
                    break
                logger.info(f"Ansible Playbook | {line.rstrip()}")

            while ansible_playbook_cmd.stderr is not None:
                line = ansible_playbook_cmd.stderr.readline().decode("utf-8")
                if not line:
                    break
                logger.error("Ansible Playbook Error | ", line.rstrip())

            # Finish ansible run
            run_ansible = False

            logger.info("Ansible Playbook finished!")
