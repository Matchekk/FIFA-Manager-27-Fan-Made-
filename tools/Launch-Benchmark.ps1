param(
    [Parameter(Mandatory=$true)][string]$GameRoot,
    [ValidateRange(3,600)][int]$WaitSeconds = 180,
    [switch]$AttachOnly
)
$ErrorActionPreference = 'Stop'
$resolved = (Resolve-Path -LiteralPath $GameRoot).Path
$manager = Join-Path $resolved 'Manager.exe'
if (-not (Test-Path -LiteralPath $manager -PathType Leaf)) { throw 'Manager.exe missing.' }
$hash = (Get-FileHash -LiteralPath $manager -Algorithm SHA256).Hash
function Find-GameProcess {
    @(Get-Process -Name Manager -ErrorAction SilentlyContinue | Where-Object {
        try { [string]::Equals($_.Path, $manager, [StringComparison]::OrdinalIgnoreCase) }
        catch { $false }
    })
}
$initial = @(Find-GameProcess)
if ($initial.Count -gt 1) { throw 'Multiple matching game processes; select a PID explicitly for measurement.' }
if ($AttachOnly -and $initial.Count -eq 0) { throw 'No running game found at the requested path.' }
$launch = $null
$creationSeconds = $null
$mode = if ($initial.Count) { 'ATTACHED_EXISTING' } else { 'LAUNCHED' }
if ($initial.Count -eq 0) {
    $creation = [Diagnostics.Stopwatch]::StartNew()
    # The normal startup can include a size-selector and process hand-off.
    # A clean exit of this first process is not evidence of a game crash.
    $launch = Start-Process -FilePath $manager -WorkingDirectory $resolved -PassThru
    $creation.Stop()
    $creationSeconds = $creation.Elapsed.TotalSeconds
}
$watch = [Diagnostics.Stopwatch]::StartNew()
$candidateId = $null
$stableSince = 0.0
$selected = $null
do {
    $candidates = @(Find-GameProcess)
    if ($candidates.Count -gt 1) { throw 'Multiple matching game processes detected; refusing an ambiguous attach.' }
    if ($candidates.Count -eq 1 -and $candidates[0].MainWindowHandle -ne 0) {
        if ($candidateId -ne $candidates[0].Id) {
            $candidateId = $candidates[0].Id
            $stableSince = $watch.Elapsed.TotalSeconds
        } elseif ($watch.Elapsed.TotalSeconds - $stableSince -ge 2) {
            $selected = $candidates[0]
            break
        }
    } else { $candidateId = $null }
    Start-Sleep -Milliseconds 250
} while ($watch.Elapsed.TotalSeconds -lt $WaitSeconds)
$watch.Stop()
$launchExit = $null
if ($null -ne $launch) {
    $launch.Refresh()
    if ($launch.HasExited) { $launchExit = $launch.ExitCode }
}
@{
    status = if ($selected) { 'GAME_WINDOW_OBSERVED' } else { 'WAIT_TIMEOUT_NOT_A_CRASH_DIAGNOSIS' }
    mode = $mode
    process_id = if ($selected) { $selected.Id } else { $null }
    window_title = if ($selected) { $selected.MainWindowTitle } else { $null }
    process_start_utc = if ($selected) { $selected.StartTime.ToUniversalTime().ToString('o') } else { $null }
    executable_sha256 = $hash
    process_creation_seconds = $creationSeconds
    launch_process_exit_code = $launchExit
    discovery_wait_seconds = $watch.Elapsed.TotalSeconds
    main_menu_seconds = $null
    note = 'A stable game window is not proof of main-menu readiness. Attached games have no startup measurement. Size-dialog time may be included in discovery wait.'
} | ConvertTo-Json
