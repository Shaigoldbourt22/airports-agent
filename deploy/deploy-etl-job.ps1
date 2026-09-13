# Creates the scheduled ETL job that rebuilds airports.db in Azure.
#
# The job and the web app share an Azure Files volume. The job writes
# airports.db there monthly; the web app reads it.
#
# BTS publishes On-Time data about ten weeks in arrears, so the 8th of each
# month is late enough that a new month is always available.
#
# Usage:  ./deploy-etl-job.ps1

$ErrorActionPreference = 'Stop'

$rg       = 'airports-agent-rg'
$env      = 'airports-agent-env'
$location = 'eastus'
$job      = 'airports-etl'
$share    = 'airportsdata'
$storage  = 'apdata46177'
$volume   = 'dbvolume'
$mount    = '/data'

$acr = az acr list -g $rg --query "[0].name" -o tsv
if (-not $acr) { throw "No container registry found in $rg" }
$image = "$acr.azurecr.io/airports-etl:latest"

Write-Host "1/5 storage account"
if (-not (az storage account show -n $storage -g $rg 2>$null)) {
    az storage account create -n $storage -g $rg -l $location `
        --sku Standard_LRS --kind StorageV2 -o none
}
$key = az storage account keys list -n $storage -g $rg --query "[0].value" -o tsv
az storage share-rm create --storage-account $storage -g $rg -n $share `
    --quota 1024 -o none 2>$null

Write-Host "2/5 mount share into the environment"
az containerapp env storage set -n $env -g $rg `
    --storage-name $volume `
    --azure-file-account-name $storage `
    --azure-file-account-key $key `
    --azure-file-share-name $share `
    --access-mode ReadWrite -o none

Write-Host "3/5 build the ETL image"
az acr build --registry $acr --image airports-etl:latest -f Dockerfile.etl . --no-logs

Write-Host "4/5 create the scheduled job"
if (az containerapp job show -n $job -g $rg 2>$null) {
    az containerapp job delete -n $job -g $rg --yes -o none
}
az containerapp job create `
    --name $job --resource-group $rg --environment $env `
    --trigger-type Schedule `
    --cron-expression "0 6 8 * *" `
    --replica-timeout 3600 `
    --replica-retry-limit 2 `
    --parallelism 1 `
    --image $image `
    --cpu 1.0 --memory 2.0Gi `
    --registry-server "$acr.azurecr.io" `
    --env-vars "DB_DIR=$mount" "BTS_MONTHS=12" `
    -o none

Write-Host "5/5 attach the volume to the job"
$yaml = az containerapp job show -n $job -g $rg -o yaml
$yaml = $yaml -replace '(?m)^(\s*)containers:', @"
`$1volumes:
`$1- name: $volume
`$1  storageName: $volume
`$1  storageType: AzureFile
`$1containers:
"@
$yaml = $yaml -replace '(?m)^(\s*)(resources:)', @"
`$1volumeMounts:
`$1- volumeName: $volume
`$1  mountPath: $mount
`$1`$2
"@
$tmp = New-TemporaryFile
$yaml | Set-Content $tmp.FullName
az containerapp job update -n $job -g $rg --yaml $tmp.FullName -o none
Remove-Item $tmp.FullName

Write-Host ""
Write-Host "Job '$job' created. Runs 06:00 UTC on the 8th of each month."
Write-Host "Run now:   az containerapp job start -n $job -g $rg"
Write-Host "History:   az containerapp job execution list -n $job -g $rg -o table"
