param(
  [string]$PhysicalPort = "COM7",
  [int[]]$VirtualPorts = @(17, 18)
)

$ErrorActionPreference = "Stop"

$pp = $PhysicalPort.Trim()
$ppNum = 0
if ($pp -match '^(?i)COM(\d+)$') {
  $ppNum = [int]$Matches[1]
} elseif ($pp -match '^\d+$') {
  $ppNum = [int]$pp
}
if ($ppNum -le 0) {
  Write-Output "ERRO: PhysicalPort inválido. Use 7 ou COM7."
  exit 1
}

$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
  Write-Output "ERRO: execute este script como Administrador."
  $vpArgs = ($VirtualPorts | ForEach-Object { "$_" }) -join " "
  Write-Output "Sugestão: Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -PhysicalPort $ppNum -VirtualPorts $vpArgs'"
  exit 1
}

$interop = "C:\Program Files\HHD Software\Virtual Serial Port Tools\api\interop\hhdvspkit.interop.dll"
if (!(Test-Path $interop)) {
  throw "interop_not_found: $interop"
}

Add-Type -Path $interop
$lib = New-Object HHDVSPKIT.SerialPortLibraryClass

foreach ($vp in $VirtualPorts) {
  $existing = @($lib.getPorts([HHDVSPKIT.SerialPortType]::Shared))
  foreach ($p in $existing) {
    try {
      if ([int]$p.port -eq $vp) {
        $p.deleteDevice()
      }
    } catch {}
  }

  $name = "COM$vp"
  try {
    $dev = $lib.createSharedPort($name)
    $dev.sharedPort = [int]$ppNum
    Write-Output "OK: criado $name compartilhando COM$ppNum"
  } catch {
    $hr = "0x{0:X8}" -f $_.Exception.HResult
    Write-Output "ERRO: falhou ao criar $name (hr=$hr). Rode este script como Administrador."
    Write-Output $_.Exception.Message
    exit 1
  }

  try {
    $p = New-Object System.IO.Ports.SerialPort $name, 115200
    $p.Open()
    $p.Close()
    Write-Output "OK: $name abre normalmente"
  } catch {
    Write-Output "AVISO: $name foi criado, mas não abriu ainda. Tente reiniciar o PC ou reiniciar o dispositivo no Gerenciador de Dispositivos."
    Write-Output ("Detalhes: " + $_.Exception.Message)
  }
}
