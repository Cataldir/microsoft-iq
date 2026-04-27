// ──────────────────────────────────────────────
// Foundry IQ — Bicep infrastructure
// Deploys: Storage Account, AI Search, AI Services
// ──────────────────────────────────────────────

@description('The Azure region for all resources.')
param location string = resourceGroup().location

@description('Unique suffix for resource names.')
param nameSuffix string = uniqueString(resourceGroup().id)

@description('SKU for Azure AI Search.')
@allowed(['free', 'basic', 'standard'])
param searchSku string = 'basic'

@description('Name of the Blob container for knowledge documents.')
param containerName string = 'knowledge-docs'

@description('Name of the AI Search index.')
param searchIndexName string = 'microsoft-iq-products'

// ── Storage Account ──────────────────────────

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: 'stmiq${nameSuffix}'
  location: location
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storageAccount
  name: 'default'
}

resource blobContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: containerName
  properties: {
    publicAccess: 'None'
  }
}

// ── Azure AI Search ──────────────────────────

resource searchService 'Microsoft.Search/searchServices@2024-03-01-preview' = {
  name: 'srch-miq-${nameSuffix}'
  location: location
  sku: { name: searchSku }
  identity: { type: 'SystemAssigned' }
  properties: {
    hostingMode: 'default'
    publicNetworkAccess: 'enabled'
    partitionCount: 1
    replicaCount: 1
    authOptions: {
      aadOrApiKey: {
        aadAuthFailureMode: 'http401WithBearerChallenge'
      }
    }
  }
}

// ── Azure AI Services (for Foundry) ──────────

resource aiServices 'Microsoft.CognitiveServices/accounts@2024-04-01-preview' = {
  name: 'ai-miq-${nameSuffix}'
  location: location
  kind: 'AIServices'
  sku: { name: 'S0' }
  identity: { type: 'SystemAssigned' }
  properties: {
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: true
    customSubDomainName: 'ai-miq-${nameSuffix}'
  }
}

// ── Role Assignments ─────────────────────────

// Search service managed identity → Cognitive Services User on AI Services
resource searchToAiRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(searchService.id, aiServices.id, 'CognitiveServicesUser')
  scope: aiServices
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      'a97b65f3-24c7-4388-baec-2e87135dc908' // Cognitive Services User
    )
    principalId: searchService.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// Search service managed identity → Storage Blob Data Reader on storage
resource searchToStorageRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(searchService.id, storageAccount.id, 'StorageBlobDataReader')
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1' // Storage Blob Data Reader
    )
    principalId: searchService.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// ── Outputs ──────────────────────────────────

output storageAccountName string = storageAccount.name
output storageContainerName string = containerName
output searchServiceName string = searchService.name
output searchServiceEndpoint string = 'https://${searchService.name}.search.windows.net'
output searchIndexName string = searchIndexName
output aiServicesEndpoint string = aiServices.properties.endpoint
output aiServicesName string = aiServices.name
