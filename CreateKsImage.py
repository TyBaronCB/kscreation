import subprocess
import os
import json
import sys
import time


def execute(command):
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
    process.wait()


def exec_out(command):
    proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE).stdout
    return proc.read().decode("utf-8")


def write_ks(data, repos):
    if data['ftp'] != "":
        repos = r"url --url=\"" + data['ftp'] + r"BaseOS/\"" + "\n" \
        r"repo --name=\"appstream\" --baseurl=" + data['ftp'] + "AppStream\n"

    ks = "auth --enableshadow --passalgo=sha512\n" \
         "autopart --type=lvm\n"\
         + repos + \
         "keyboard --vckeymap="+ data['key_board_layout'] + " --xlayouts=\'" + data['key_board_layout'] + "\'\n"\
         "clearpart --all --initlabel\n"\
         "network  --bootproto=dhcp --onboot=on --ipv6=auto\n"\
         "network  --hostname=localhost.localdomain\n"\
         "lang en_US.UTF-8\n"\
         r'services --enabled=\"chronyd\"'+'\n'\
         "timezone America/New_York --isUtc\n"\
         "xconfig  --startxonboot\n"

    if data['Auto_boot']:
        ks += 'firstboot --disabled\n'
    else:
        ks += 'firstboot --enabled\n'
    ks += 'rootpw ' + data['root_password'] + '\n'
    if data['reboot']:
        ks += 'reboot\n'
    ks += "%packages\n"
    ks += "@^" + data['install_type'] + "\n"
    for packages in data['packages']:
        ks += packages + '\n'
    ks += "@core\n" \
          "chrony\n" \
          "kexec-tools\n" \
          "kexec-tools\n" \
          "%end\n" \
          "%addon com_redhat_kdump --enable #--reserve-mb =\'auto\'\n"\
          "%end\n"\
          "%anaconda\n"\
          "pwpolicy root --minlen=6 --minquality=1 --notstrict --nochanges --notempty\n"\
          "pwpolicy user --minlen=6 --minquality=1 --notstrict --nochanges --emptyok\n"\
          "pwpolicy luks --minlen=6 --minquality=1 --notstrict --nochanges --notempty\n"\
          "%end\n"
    return ks

# if os.name == 'nt':
#     print("cannot run script on windows")
#     exit(0)


if '-i' not in sys.argv or '-c' not in sys.argv:
    print("Script must be run with -i flag with iso image and -c flag with json config")
    print("\n\tpython3 CreateKsImage.py -i <ISO> -c <config.json>")
    exit(0)

config_index = -1
image_index = -1
output_index = -1
for i in range(len(sys.argv)):
    if sys.argv[i] == '-c':
        config_index = i+1
    elif sys.argv[i] == '-i':
        image_index = i+1
    elif sys.argv[i] == '-o':
        output_index = i+1

try:
    image = sys.argv[image_index]
except:
    print("Error: no file provided")
    exit(0)

try:
    config = sys.argv[config_index]
except:
    print("Error: no file provided")
    exit(0)

if output_index != -1:

    try:
        output_iso = sys.argv[output_index]
    except:
        print("Error: no output file provided")
        exit(0)
else:
    output_iso = "newKS.iso"

if config.split('.')[-1].lower() != "json":
    print("Error: invalid config file type")
    exit(0)
if image.split('.')[-1].lower() != 'iso':
    print("Error: invalid image file type")
    exit(0)

execute('umount /mnt')
execute('mount -o loop ' + image + ' /mnt')
execute('yes | rm -r tmp')
execute('mkdir tmp')
execute('cp -r /mnt/* tmp/')
execute('touch ks.cfg')
volume_id = exec_out(r'iso-info -d -i ' + image + ' | grep \"Volume\" | sed -e \'s/Volume//\' -e \'s//' + r"\\x20/g' -e 's/ //g'")[:-1]

print(volume_id)

timeout = '50'
label_section = False
remove_label_section = True
set_timeout = True
new_bios_config = ''
bios_config = open("tmp/isolinux/isolinux.cfg", "r+")
for line in bios_config:
    if "menu separator" in line and remove_label_section and label_section:
        remove_label_section = False
        label_section = False
        line = "label linux ks\n" \
  		"  menu label ^Install "+ volume_id + "\n" \
		"  menu default\n" \
 		"  kernel vmlinuz\n" \
  		"  append initrd=initrd.img inst.stage2=hd:LABEL=" + volume_id + " quiet inst.ks=hd:LABEL=" + volume_id + ":/ks.cfg\n"

    elif "timeout " in line and set_timeout:
        line = "timeout " + timeout
        set_timeout = False
    elif "label" in line and remove_label_section:
        label_section = True
    if not label_section:
        new_bios_config += line
w = open("tmp/isolinux/isolinux.cfg", "w+")
w.write(new_bios_config)
w.close()
bios_config.close()

timeout = '3'
label_section = False
remove_label_section = True
set_timeout = True
new_uefi_config = ''
uefi_config = open("tmp/EFI/BOOT/grub.cfg", "r+")
for line in uefi_config:
    if "submenu" in line and remove_label_section and label_section:
        remove_label_section = False
        label_section = False
        line = "\tmenuentry \'Install "+ volume_id + "\'--class fedora --class gnu-linux --class gnu --class os {\n\tlinuxefi /images/pxeboot/vmlinuz inst.ks=hd:LABEL=" + volume_id + ":/ks.cfg inst.stage2=hd:LABEL=" + volume_id + " quiet\n\t initrdefi /images/pxeboot/initrd.img\n}\n"
    elif "set default" in line:
        line = "set default=\"0\""
    elif "set timeout" in line:
        line = "set timeout=" + timeout
    elif "menuentry" in line and remove_label_section:
        label_section = True
    if not label_section:
        new_uefi_config += line
w = open("tmp/EFI/BOOT/grub.cfg", "w+")
w.write(new_uefi_config)
w.close()
uefi_config.close()

repos = ''
# extract appstream populate repos
if "RHEL-8" in volume_id or "RHEL-9" in volume_id:
    #if data['ftp'] is not "":
    execute('rm -r tmp/AppStream')
    #else:
    #execute('cp -r tmp/BaseOS/* tmp')
    execute('rm -r tmp/BaseOS')
    #repos = r'repo --name=\"BaseOS\" --baseurl=file:///run/install/repo/BaseOS'+'\n'
if "RHEL-7" in volume_id:
    repos = r'repo --name=\"AppStream\" --baseurl=file:///run/install/repo/Appstream'+'\n'
    + r'repo --name=\"Server-HighAvailability\" --baseurl=file:///run/install/repo/addons/HighAvailability'+'\n'
    + r'repo --name=\"Server-ResilientStorage\" --baseurl=file:///run/install/repo/addons/ResilientStorage'+'\n'
with open(config) as f:
  data = json.load(f)

ks = write_ks(data, repos)
execute('echo \"' + ks + '\" > ks.cfg')
time.sleep(10)
execute('cp ks.cfg tmp/')

formated_volume = volume_id.replace(r'\x20', ' ')

execute("mkisofs -J -joliet-long -T -o /root/" + output_iso + " -b isolinux/isolinux.bin -c isolinux/boot.cat -no-emul-boot -boot-load-size 4 -boot-info-table -R -m TRANS.TBL -graft-points -V \"" + formated_volume + "\" tmp/")

print("mkisofs -J -joliet-long -T -o /root/" + output_iso + " -b isolinux/isolinux.bin -c isolinux/boot.cat -no-emul-boot -boot-load-size 4 -boot-info-table -R -m TRANS.TBL -graft-points -V \"" + formated_volume + "\" tmp/")
