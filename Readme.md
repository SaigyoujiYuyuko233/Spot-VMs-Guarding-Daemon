## Spot Vms Init Daemon

一个简单的脚本。通过持续检查 Terraform state 来判断 抢占实例 是否被销毁。并且在销毁后重新创建。  
安装/使用教程在后面。

## 使用场景

### 联机打游戏
我不想长期租一个服务器来跑游戏服务，对我来说没必要，也因为服务器配置太贵了。  
我想在有需求时 L7 转发 (Frp / SSH Tunnel) 来让别人访问我本地的局域网游戏。

### 无状态的服务 / 流量转发
我家里有 HomeLab 并且上面跑了些服务，但是碍于没有公网无法向外暴露。  
我需要一个稳定的转发服务，并且还想省点钱。因此我选择了 抢占式实例，但是我担心突然被回收。

## 支持
- 阿里云

理论上你可以用 Terraform 去整任何你想整的，也可以把这个脚本当做一个防止配置漂移的工具。  
但是此脚本会具体检测 Terraform state -> resources 下 云服务厂商 的 Instance 标记 (Ex: alicloud_instance)  
也因为每个厂商的字段都不一样，脚本有一些地方是写死的 (考虑到可能就我一个人用)。  
如果有需要可以发 issue，我看到了会弄的。

## 运行流程
当 "./main guard" 被执行后:
1. 目录/文件检查
   - Terraform 目录 / main.tf 文件
   - Ansible 目录 / inventory / playbook
2. 初始化 Terraform (``tofu init``)
   - 可以通过 ``--skip-tf-init`` 跳过
3. 判断当前 tf state 是否跟远端一致 (``tofu plan -detailed-exitcode``)
   - 一致则跳转到 #5
4. 执行 ``tofu apply`` 
5. 当用户指定 ``--run-ansible`` 或者实例是刚创建的则运行 Ansible
   - 2个条件都失败后跳转到 #3 并等待 30 秒 (``--interval=30``)
6. 读取 ``user_config/ansible/user-inventory.ini``
7. 将文件中的 ``%instance_ip%`` 替换为实例 IP
8. 在 ansible 目录下生成 ``inventory-gen.ini``
9. 运行 Playbook (``--ansible-playbook=require_value.yaml``)

## Installation
Within a particular ecosystem, there may be a common way of installing things, such as using Yarn, NuGet, or Homebrew. However, consider the possibility that whoever is reading your README is a novice and would like more guidance. Listing specific steps helps remove ambiguity and gets people to using your project as quickly as possible. If it only runs in a specific context like a particular programming language version or operating system or has dependencies that have to be installed manually, also add a Requirements subsection.

## Usage
Use examples liberally, and show the expected output if you can. It's helpful to have inline the smallest example of usage that you can demonstrate, while providing links to more sophisticated examples if they are too long to reasonably include in the README.

## Support
Tell people where they can go to for help. It can be any combination of an issue tracker, a chat room, an email address, etc.

## Roadmap
If you have ideas for releases in the future, it is a good idea to list them in the README.

## Contributing
State if you are open to contributions and what your requirements are for accepting them.

For people who want to make changes to your project, it's helpful to have some documentation on how to get started. Perhaps there is a script that they should run or some environment variables that they need to set. Make these steps explicit. These instructions could also be useful to your future self.

You can also document commands to lint the code or run tests. These steps help to ensure high code quality and reduce the likelihood that the changes inadvertently break something. Having instructions for running tests is especially helpful if it requires external setup, such as starting a Selenium server for testing in a browser.

## Authors and acknowledgment
Show your appreciation to those who have contributed to the project.

## License
For open source projects, say how it is licensed.

## Project status
If you have run out of energy or time for your project, put a note at the top of the README saying that development has slowed down or stopped completely. Someone may choose to fork your project or volunteer to step in as a maintainer or owner, allowing your project to keep going. You can also make an explicit request for maintainers.

