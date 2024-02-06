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

## 安装和使用

### 依赖
- Terraform
- Ansible
- Python

### 安装 & 使用
1. Clone 本仓库
2. ``pip install -r requirements.txt``
3. ``python main.py guard -vvv`` (强烈推荐添加 -vvv)

## 一些见解
main.tf 里面不只可以写你的云实例，你还可以...

### DDNS?
拿 Cloudflare 举例，这是他的 provider
```terraform
 cloudflare = {
   source  = "cloudflare/cloudflare"
   version = "~> 4.0"
 }
```
然后配置下你的 token
```terraform
provider "cloudflare" {
  api_token = "ciallo"
}
```
最后添加解析
```terraform
resource "cloudflare_record" "ddns" {
  zone_id = "Gensokyo"
  name    = "my-vm"
  value   = alicloud_instance.你的label.public_ip
  type    = "A"
  ttl     = 60

  depends_on = [
    alicloud_instance.你的label,
  ]
}
```

### 添加阿里云的 SSH 公钥
这样子你就可以流畅使用 Ansible 了
```terraform
resource "alicloud_ecs_key_pair" "你的pubkey_label" {
  key_pair_name = "my-ssh-pubkey-for-ansible"
  public_key    = "ssh-ed25519 AAAAxxxxxx"
}
```

```terraform
resource "alicloud_ecs_key_pair_attachment" "你的label" {
  key_pair_name = alicloud_ecs_key_pair.你的pubkey_label.key_pair_name
  instance_ids  = [alicloud_instance.你的label.id]

  depends_on = [
    alicloud_instance.你的label,
    alicloud_ecs_key_pair.你的pubkey_label
  ]
}
```

### 你不止可以 Ansible 刚创建的实例
比如说我有一台软路由，我想部署下客户端什么的，你可以整 Ansible

最后强烈建议去看下 ``example_config`` 里面的一些操作。

## 支持
直接发 Issue

## 未来计划
- 可能会支持其他的提供商
- 封装个 Docker 镜像
- 分享点 Ansible playbook

## 共享
欢迎 PR  
欢迎制作更多的例子，比如说 Frp 什么的 ansible playbook 到 ``example_config`` 里面
