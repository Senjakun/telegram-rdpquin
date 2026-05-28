#!/bin/bash
# ============================================
# RDP Auto Installer - QEMU/KVM
# Support 13 Windows OS
# Usage: ./rdp.sh <IP> <PASSWORD> <OS_NUMBER>
# ============================================

IP="$1"
PASS="$2"
OS_NUM="$3"
RDP_USER="Administrator"
RDP_PASS="P@ssw0rd123"
RAM="2048"
DISK="40G"
CPU="2"

if [ -z "$IP" ] || [ -z "$PASS" ] || [ -z "$OS_NUM" ]; then
    echo "Usage: ./rdp.sh <IP> <PASSWORD> <OS_NUMBER>"
    exit 1
fi

# ============================================
# CUSTOM MIRROR (opsional)
# Set URL mirror kamu di sini. ISO harus dinamai:
#   win2012r2.iso, win2016.iso, win2019.iso, win2022.iso, win2025.iso,
#   win10-superlite.iso, win11-superlite.iso, win10-atlas.iso,
#   win11-atlas.iso, win10-pro.iso, win11-pro.iso, tiny10.iso, tiny11.iso
# Contoh: MIRROR_URL="https://your-server.com/iso"
# ============================================
MIRROR_URL=""

# ============================================
# ISO LINKS (Public mirrors / archive.org)
# ============================================
get_iso_filename() {
    case "$OS_NUM" in
        1) echo "win2012r2.iso";;
        2) echo "win2016.iso";;
        3) echo "win2019.iso";;
        4) echo "win2022.iso";;
        5) echo "win2025.iso";;
        6) echo "win10-superlite.iso";;
        7) echo "win11-superlite.iso";;
        8) echo "win10-atlas.iso";;
        9) echo "win11-atlas.iso";;
        10) echo "win10-pro.iso";;
        11) echo "win11-pro.iso";;
        12) echo "tiny10.iso";;
        13) echo "tiny11.iso";;
    esac
}

get_iso_url() {
    # Kalau MIRROR_URL diset, pakai mirror
    if [ -n "$MIRROR_URL" ]; then
        echo "${MIRROR_URL}/$(get_iso_filename)"
        return
    fi
    case "$OS_NUM" in
        1) echo "https://download.microsoft.com/download/6/2/A/62A76ABB-9990-4EFC-A4FE-C7D698DAEB96/9600.17050.WINBLUE_REFRESH.140317-1640_X64FRE_SERVER_EVAL_EN-US-IR3_SSS_X64FREE_EN-US_DV9.ISO";;
        2) echo "https://software-static.download.prss.microsoft.com/pr/download/Windows_Server_2016_Datacenter_EVAL_en-us_14393_refresh.ISO";;
        3) echo "https://software-static.download.prss.microsoft.com/dbazure/988969d5-f34g-4e03-ac9d-1f9786c66749/17763.3650.221105-1748.rs5_release_svc_refresh_SERVER_EVAL_x64FRE_en-us.iso";;
        4) echo "https://software-static.download.prss.microsoft.com/sg/download/888969d5-f34g-4e03-ac9d-1f9786c66749/SERVER_EVAL_x64FRE_en-us.iso";;
        5) echo "https://software-static.download.prss.microsoft.com/dbazure/888969d5-f34g-4e03-ac9d-1f9786c66749/26100.1742.240906-0331.ge_release_svc_refresh_SERVER_EVAL_x64FRE_en-us.iso";;
        6) echo "https://archive.org/download/win-10-super-lite/Win10_SuperLite.iso";;
        7) echo "https://archive.org/download/ghost-spectre-windows-11-u2-u6-lite-and-optimized-versions/GHOST%20SPECTRE%20WIN11%20%28U2-U6%29/SUPERLITE/WIN11.SUPERLITE.24H2.U6.X64.%28WPE%29.ISO";;
        8) echo "https://archive.org/download/win-10-22-h-2-atlas-os-net-full-x-64/Win10_22H2_Atlas_OS_Net-Full_x64.iso";;
        9) echo "https://archive.org/download/ghost-spectre-windows-11-pro-23-h-2-update-26-64-bit/Ghost%20Spectre%20Windows%2011%20Pro%2023H2%20Update%2026%20%2864-bit%29.ISO";;
        10) echo "https://archive.org/download/ghost-spectre-windows-10-aio-update-36/Ghost%20Spectre%20Windows%2010%20AIO%20Update%2036.ISO";;
        11) echo "https://archive.org/download/ghost-spectre-windows-11-u2-u6-lite-and-optimized-versions/GHOST%20SPECTRE%20WIN11%20%28U2-U6%29/PRO/WIN11.PRO.24H2.U6.X64.%28WPE%29.ISO";;
        12) echo "https://archive.org/download/tiny-10-23-h2/tiny10%20x64%2023h2.iso";;
        13) echo "https://archive.org/download/tiny11-2311/tiny11%202311%20x64.iso";;
        *) echo ""; exit 1;;
    esac
}

get_os_name() {
    case "$OS_NUM" in
        1) echo "Windows Server 2012 R2";;
        2) echo "Windows Server 2016";;
        3) echo "Windows Server 2019";;
        4) echo "Windows Server 2022";;
        5) echo "Windows Server 2025";;
        6) echo "Windows 10 SuperLite";;
        7) echo "Windows 11 SuperLite";;
        8) echo "Windows 10 Atlas";;
        9) echo "Windows 11 Atlas";;
        10) echo "Windows 10 Pro";;
        11) echo "Windows 11 Pro";;
        12) echo "Tiny10 23H2";;
        13) echo "Tiny11 23H2";;
    esac
}

ISO_URL=$(get_iso_url)
OS_NAME=$(get_os_name)

if [ -z "$ISO_URL" ]; then
    echo "ERROR: Invalid OS number"
    exit 1
fi

echo "============================================"
echo " RDP Installer"
echo " Target: $IP"
echo " OS: $OS_NAME"
echo "============================================"

# ============================================
# SSH & INSTALL VIA REMOTE
# ============================================
sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@"$IP" bash -s <<REMOTE_SCRIPT

set -e
export DEBIAN_FRONTEND=noninteractive

# Detect package manager
if command -v apt-get &>/dev/null; then
    PKG_MGR="apt"
elif command -v dnf &>/dev/null; then
    PKG_MGR="dnf"
elif command -v yum &>/dev/null; then
    PKG_MGR="yum"
else
    echo "ERROR: No supported package manager found (apt/dnf/yum)"
    exit 1
fi

echo "[1/6] Updating system..."
if [ "\$PKG_MGR" = "apt" ]; then
    apt-get update -qq
    apt-get upgrade -y -qq
else
    \$PKG_MGR update -y -q
fi

echo "[2/6] Installing QEMU/KVM & dependencies..."
if [ "\$PKG_MGR" = "apt" ]; then
    apt-get install -y -qq qemu-kvm qemu-utils libvirt-daemon-system \
        virtinst bridge-utils wget ovmf sshpass net-tools
else
    \$PKG_MGR install -y -q qemu-kvm qemu-img libvirt virt-install \
        bridge-utils wget edk2-ovmf sshpass net-tools
fi

systemctl enable --now libvirtd 2>/dev/null || true

echo "[3/6] Creating virtual disk..."
mkdir -p /root/rdp
qemu-img create -f qcow2 /root/rdp/windows.qcow2 $DISK

echo "[4/6] Downloading Windows ISO: $OS_NAME..."
wget --tries=3 --timeout=60 --waitretry=5 -q --show-progress -O /root/rdp/windows.iso "$ISO_URL" || { echo "ERROR: Failed to download ISO"; exit 1; }

echo "[5/6] Downloading VirtIO drivers..."
wget --tries=3 --timeout=60 --waitretry=5 -q --show-progress -O /root/rdp/virtio-win.iso "https://fedorapeople.org/groups/virt/virtio-win/direct-downloads/stable-virtio/virtio-win.iso" || { echo "ERROR: Failed to download VirtIO"; exit 1; }

echo "[6/6] Starting Windows VM installation..."

# Create autounattend for unattended install
cat > /root/rdp/autounattend.xml <<'EOF'
<?xml version="1.0" encoding="utf-8"?>
<unattend xmlns="urn:schemas-microsoft-com:unattend">
  <settings pass="windowsPE">
    <component name="Microsoft-Windows-International-Core-WinPE" processorArchitecture="amd64" language="neutral" xmlns:wcm="http://schemas.microsoft.com/WMIConfig/2002/State">
      <SetupUILanguage><UILanguage>en-US</UILanguage></SetupUILanguage>
      <InputLocale>en-US</InputLocale>
      <SystemLocale>en-US</SystemLocale>
      <UILanguage>en-US</UILanguage>
      <UserLocale>en-US</UserLocale>
    </component>
    <component name="Microsoft-Windows-Setup" processorArchitecture="amd64" language="neutral" xmlns:wcm="http://schemas.microsoft.com/WMIConfig/2002/State">
      <DiskConfiguration>
        <Disk wcm:action="add">
          <CreatePartitions>
            <CreatePartition wcm:action="add">
              <Order>1</Order>
              <Size>500</Size>
              <Type>EFI</Type>
            </CreatePartition>
            <CreatePartition wcm:action="add">
              <Order>2</Order>
              <Extend>true</Extend>
              <Type>Primary</Type>
            </CreatePartition>
          </CreatePartitions>
          <ModifyPartitions>
            <ModifyPartition wcm:action="add">
              <Order>1</Order>
              <PartitionID>1</PartitionID>
              <Format>FAT32</Format>
              <Label>EFI</Label>
            </ModifyPartition>
            <ModifyPartition wcm:action="add">
              <Order>2</Order>
              <PartitionID>2</PartitionID>
              <Format>NTFS</Format>
              <Label>Windows</Label>
            </ModifyPartition>
          </ModifyPartitions>
          <DiskID>0</DiskID>
          <WillWipeDisk>true</WillWipeDisk>
        </Disk>
      </DiskConfiguration>
      <ImageInstall>
        <OSImage>
          <InstallTo>
            <DiskID>0</DiskID>
            <PartitionID>2</PartitionID>
          </InstallTo>
        </OSImage>
      </ImageInstall>
      <UserData>
        <AcceptEula>true</AcceptEula>
        <ProductKey><WillShowUI>Never</WillShowUI></ProductKey>
      </UserData>
    </component>
  </settings>
  <settings pass="specialize">
    <component name="Microsoft-Windows-TerminalServices-LocalSessionManager" processorArchitecture="amd64" language="neutral" xmlns:wcm="http://schemas.microsoft.com/WMIConfig/2002/State">
      <fDenyTSConnections>false</fDenyTSConnections>
    </component>
    <component name="Networking-MPSSVC-Svc" processorArchitecture="amd64" language="neutral" xmlns:wcm="http://schemas.microsoft.com/WMIConfig/2002/State">
      <FirewallGroups>
        <FirewallGroup wcm:action="add" wcm:keyValue="RemoteDesktop">
          <Active>true</Active>
          <Group>Remote Desktop</Group>
          <Profile>all</Profile>
        </FirewallGroup>
      </FirewallGroups>
    </component>
  </settings>
  <settings pass="oobeSystem">
    <component name="Microsoft-Windows-Shell-Setup" processorArchitecture="amd64" language="neutral" xmlns:wcm="http://schemas.microsoft.com/WMIConfig/2002/State">
      <OOBE>
        <HideEULAPage>true</HideEULAPage>
        <HideLocalAccountScreen>true</HideLocalAccountScreen>
        <HideOnlineAccountScreens>true</HideOnlineAccountScreens>
        <HideWirelessSetupInOOBE>true</HideWirelessSetupInOOBE>
        <ProtectYourPC>3</ProtectYourPC>
      </OOBE>
      <UserAccounts>
        <AdministratorPassword>
          <Value>$RDP_PASS</Value>
          <PlainText>true</PlainText>
        </AdministratorPassword>
      </UserAccounts>
      <AutoLogon>
        <Enabled>true</Enabled>
        <Username>Administrator</Username>
        <Password><Value>$RDP_PASS</Value><PlainText>true</PlainText></Password>
      </AutoLogon>
    </component>
  </settings>
</unattend>
EOF

# Create floppy image with autounattend
mkdir -p /root/rdp/floppy
cp /root/rdp/autounattend.xml /root/rdp/floppy/autounattend.xml

# Detect OVMF path
if [ -f /usr/share/ovmf/OVMF.fd ]; then
    OVMF_PATH="/usr/share/ovmf/OVMF.fd"
elif [ -f /usr/share/OVMF/OVMF_CODE.fd ]; then
    OVMF_PATH="/usr/share/OVMF/OVMF_CODE.fd"
elif [ -f /usr/share/edk2/ovmf/OVMF_CODE.fd ]; then
    OVMF_PATH="/usr/share/edk2/ovmf/OVMF_CODE.fd"
else
    echo "ERROR: OVMF firmware not found"
    exit 1
fi

# Launch QEMU VM
qemu-system-x86_64 \
    -enable-kvm \
    -m $RAM \
    -smp $CPU \
    -cpu host \
    -hda /root/rdp/windows.qcow2 \
    -cdrom /root/rdp/windows.iso \
    -drive file=/root/rdp/virtio-win.iso,media=cdrom,index=2 \
    -boot d \
    -bios \$OVMF_PATH \
    -net nic,model=virtio \
    -net user,hostfwd=tcp::3389-:3389 \
    -vnc :0 \
    -daemonize \
    -name "Windows-RDP"

echo ""
echo "============================================"
echo " ✅ VM STARTED SUCCESSFULLY!"
echo "============================================"
echo " RDP Address : \$(hostname -I | awk '{print \$1}'):3389"
echo " Username    : $RDP_USER"
echo " Password    : $RDP_PASS"
echo " VNC Access  : \$(hostname -I | awk '{print \$1}'):5900"
echo "============================================"
echo ""
echo " ⏳ Windows sedang install otomatis..."
echo " Tunggu 15-30 menit sampai RDP bisa diakses."
echo "============================================"

REMOTE_SCRIPT

echo ""
echo "============================================"
echo " ✅ INSTALASI SELESAI!"
echo "============================================"
echo " RDP: $IP:3389"
echo " User: $RDP_USER"
echo " Pass: $RDP_PASS"
echo "============================================"
