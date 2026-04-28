using 'main.bicep'

param location = 'centralus'
param searchSku = 'basic'
param containerName = 'kaggle-data'
param searchIndexName = 'ecommerce-knowledge'
// deployerPrincipalId is passed via CLI: --parameters deployerPrincipalId=<object-id>
