# Update-OpenCodeConfig.ps1
param(
    [string]$Model = "ollama/lfm2.5:latest"
)

$filePath = "opencode.json"

# Just trim whitespace
$Model = $Model.Trim()

if (Test-Path $filePath) {
    # Read existing config
    $json = Get-Content $filePath -Raw | ConvertFrom-Json
    
    # Just update the model, keep everything else
    $json.model = $Model
    
    $json | ConvertTo-Json -Depth 10 | Set-Content $filePath
    Write-Host "Updated model to: $Model"
} else {
    # Create minimal config
    $config = [PSCustomObject]@{
        model = $Model
    }
    $config | ConvertTo-Json -Depth 10 | Set-Content $filePath
    Write-Host "Created opencode.json with model: $Model"
}
