param(
    [Parameter(Mandatory=$true)][int]$ProcessId,
    [Parameter(Mandatory=$true)][string]$GameRoot,
    [Parameter(Mandatory=$true)][string]$Output,
    [ValidateSet('startup','career_creation','save_load','save','day','week','month','deadline_day','season_transition','player_search','transfer_list','staff_list','observation')]
    [string]$Scenario = 'observation',
    [ValidateRange(1,3600)][int]$Seconds = 30,
    [string]$WorkloadId = 'unspecified',
    [string]$GraphicsProfile = 'installed-unmodified',
    [switch]$UntilEnter
)
$ErrorActionPreference = 'Stop'
$gamePath = (Resolve-Path -LiteralPath $GameRoot).Path.TrimEnd('\')
$exePath = Join-Path $gamePath 'Manager.exe'
$outputPath = [IO.Path]::GetFullPath($Output)
if ($outputPath.StartsWith($gamePath + '\', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Benchmark output must be outside the game installation.'
}
if (Test-Path -LiteralPath $outputPath) { throw 'Output already exists; use a unique run filename.' }
if ($UntilEnter -and [Console]::IsInputRedirected) { throw 'Manual timing requires an interactive console.' }
$process = Get-Process -Id $ProcessId
$processStart = $process.StartTime.ToUniversalTime().ToString('o')
if (-not [string]::Equals($process.Path, $exePath, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'PID does not belong to the requested Manager.exe.'
}
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class FM27ReadOnlyIo {
    [StructLayout(LayoutKind.Sequential)]
    public struct Counters {
        public ulong ReadOperations, WriteOperations, OtherOperations;
        public ulong ReadBytes, WriteBytes, OtherBytes;
    }
    [DllImport("kernel32.dll", SetLastError=true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool GetProcessIoCounters(IntPtr process, out Counters result);
}
'@
function Sample-Process {
    $process.Refresh()
    if ($process.HasExited) { throw 'Process exited during measurement.' }
    $io = [FM27ReadOnlyIo+Counters]::new()
    if (-not [FM27ReadOnlyIo]::GetProcessIoCounters($process.Handle, [ref]$io)) {
        throw 'Unable to read process IO counters.'
    }
    @{
        utc = [DateTime]::UtcNow.ToString('o')
        cpu_seconds = $process.TotalProcessorTime.TotalSeconds
        working_set = $process.WorkingSet64
        peak_working_set = $process.PeakWorkingSet64
        private_bytes = $process.PrivateMemorySize64
        virtual_bytes = $process.VirtualMemorySize64
        io_read_bytes = $io.ReadBytes
        io_write_bytes = $io.WriteBytes
        io_read_operations = $io.ReadOperations
        io_write_operations = $io.WriteOperations
        virtual_memory_warning = ($process.VirtualMemorySize64 -gt 3GB)
    }
}
if ($UntilEnter) {
    Read-Host 'Prepare the scenario. Press Enter to start timing, perform the action, then press Enter here when it finishes' | Out-Null
}
$samples = [System.Collections.Generic.List[object]]::new()
$status = if ($UntilEnter) { 'MANUAL_BOUNDARIES' } else { 'OBSERVATION_ONLY' }
$failure = $null
$watch = [Diagnostics.Stopwatch]::StartNew()
try {
    do {
        $samples.Add((Sample-Process))
        if ($UntilEnter -and [Console]::KeyAvailable -and [Console]::ReadKey($true).Key -eq 'Enter') { break }
        Start-Sleep -Milliseconds 250
    } while ($watch.Elapsed.TotalSeconds -lt $Seconds)
    if ($UntilEnter -and $watch.Elapsed.TotalSeconds -ge $Seconds) { $status = 'TIMEOUT_INCOMPLETE' }
} catch { $status = 'FAILED'; $failure = $_.Exception.Message }
$watch.Stop()
$first = if ($samples.Count) { $samples[0] } else { $null }
$last = if ($samples.Count) { $samples[$samples.Count - 1] } else { $null }
$summary = $null
if ($samples.Count -ge 2) {
    $summary = @{
        wall_seconds = $watch.Elapsed.TotalSeconds
        cpu_seconds = $last.cpu_seconds - $first.cpu_seconds
        io_read_bytes = $last.io_read_bytes - $first.io_read_bytes
        io_write_bytes = $last.io_write_bytes - $first.io_write_bytes
        max_working_set = ($samples | Measure-Object working_set -Maximum).Maximum
        max_private_bytes = ($samples | Measure-Object private_bytes -Maximum).Maximum
        max_virtual_bytes = ($samples | Measure-Object virtual_bytes -Maximum).Maximum
    }
}
$result = @{
    schema_version = 1; status = $status; error = $failure; scenario = $Scenario
    workload_id = $WorkloadId; graphics_profile = $GraphicsProfile
    executable_sha256 = (Get-FileHash -LiteralPath $exePath -Algorithm SHA256).Hash.ToLowerInvariant()
    executable_version = (Get-Item -LiteralPath $exePath).VersionInfo.FileVersion
    process_id = $ProcessId; process_start_utc = $processStart
    summary = $summary; samples = @($samples.ToArray())
    limitations = @('IO bytes are process IO, not physical disk throughput.',
        'Manual boundaries include human reaction/console switching and 250ms sampling error.',
        'Fixed-duration observations are not scenario latency benchmarks.',
        '3GB warning is a diagnostic threshold, not a prediction of allocation failure.')
}
[IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($outputPath)) | Out-Null
$result | ConvertTo-Json -Depth 7 | Set-Content -LiteralPath $outputPath -Encoding UTF8
Write-Output "Recorded $($samples.Count) samples; status=$status; $outputPath"
