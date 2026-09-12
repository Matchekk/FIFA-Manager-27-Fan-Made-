param([Parameter(Mandatory=$true)][string]$GameRoot)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$issues = [System.Collections.Generic.List[string]]::new()
function Read-Class([string]$Name, [string[]]$Fields) {
    try { @(Get-CimInstance -ClassName $Name | Select-Object -Property $Fields) }
    catch { $issues.Add("${Name}: $($_.Exception.Message)"); @() }
}
$executables = @(Get-ChildItem -LiteralPath $GameRoot -File | Where-Object Extension -eq '.exe' | ForEach-Object {
    @{name=$_.Name; file_version=$_.VersionInfo.FileVersion; product=$_.VersionInfo.ProductName}
})
$storage = @()
try { $storage = @(Get-PhysicalDisk | Select-Object FriendlyName,MediaType,BusType,Size) }
catch { $issues.Add("Storage: $($_.Exception.Message)") }
@{
    os = @(Read-Class Win32_OperatingSystem @('Caption','Version','BuildNumber','OSArchitecture','TotalVisibleMemorySize'))
    cpu = @(Read-Class Win32_Processor @('Name','NumberOfCores','NumberOfLogicalProcessors','MaxClockSpeed'))
    gpu = @(Read-Class Win32_VideoController @('Name','AdapterRAM','DriverVersion'))
    storage = $storage
    executables = $executables
    gpu_memory_caveat = 'AdapterRAM is driver-reported uint32; not a reliable dedicated/shared VRAM budget, especially on integrated GPUs.'
    errors = @($issues)
} | ConvertTo-Json -Depth 6
