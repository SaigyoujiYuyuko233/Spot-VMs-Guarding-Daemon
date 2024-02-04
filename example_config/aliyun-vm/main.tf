terraform {
  required_providers {
    aliyun = {
      source  = "aliyun/alicloud"
      version = "~> 1.217.0"
    }
  }
}

provider "aliyun" {
  access_key = "accId"
  secret_key = "accKey"
  region     = "cn-shenzhen"
}

resource "alicloud_instance" "example_instance" {
  instance_name = "example"
  host_name     = "ciallo-vm"
  password      = "c1all0~(<.w<)n!"

  image_id                      = "fedora_39_x64_20G_alibase_20231121.vhd"
  instance_type                 = "ecs.t5-lc2m1.nano"
  security_groups               = ["sg-example"]
  vswitch_id                    = "vsw-example"
  internet_max_bandwidth_out    = "5"
  system_disk_size              = "20"
  system_disk_category          = "cloud_efficiency"
  security_enhancement_strategy = "Deactive"
  #data_disks {}

  instance_charge_type = "PostPaid"
  internet_charge_type = "PayByTraffic"
  spot_strategy        = "SpotWithPriceLimit"
  spot_price_limit     = "0.02"
  spot_duration        = "1"
}
