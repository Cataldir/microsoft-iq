// ──────────────────────────────────────────────
// Foundry IQ — Bicep infrastructure (swedencentral)
// Deploys: Storage, AI Search (semantic), AI Services,
//          AI Foundry Project (Agents V2),
//          GPT model deployment, full RBAC matrix
// ──────────────────────────────────────────────

@description('Azure region for all resources (swedencentral for Agents + GPT model access).')
param location string = 'swedencentral'

@description('Unique suffix for resource names.')
param nameSuffix string = uniqueString(resourceGroup().id)

@description('SKU for Azure AI Search.')
@allowed(['basic', 'standard'])
param searchSku string = 'basic'

@description('Name of the Blob container for Kaggle data.')
param containerName string = 'kaggle-data'

@description('Name of the AI Search index.')
param searchIndexName string = 'ecommerce-knowledge'

@description('Object ID of the deploying user (for RBAC on data-plane operations).')
param deployerPrincipalId string

// ── RBAC Role Definition IDs ─────────────────

var storageBlobDataContributor = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
var storageBlobDataReader      = '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1'
var cognitiveServicesUser      = 'a97b65f3-24c7-4388-baec-2e87135dc908'
var cognitiveServicesOpenAIUser = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
var searchIndexDataReader      = '1407120a-92aa-4202-b7e9-c0e197c71c8f'
var searchIndexDataContributor = '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
var searchServiceContributor   = '7ca78c08-252a-4471-8644-bb5ff32d4ba0'

// ══════════════════════════════════════════════
// RESOURCES
// ══════════════════════════════════════════════

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

// ── Azure AI Search (semantic search enabled) ─

resource searchService 'Microsoft.Search/searchServices@2024-06-01-preview' = {
  name: 'srch-miq-${nameSuffix}'
  location: location
  sku: { name: searchSku }
  identity: { type: 'SystemAssigned' }
  properties: {
    hostingMode: 'default'
    publicNetworkAccess: 'enabled'
    partitionCount: 1
    replicaCount: 1
    semanticSearch: 'free'
    authOptions: {
      aadOrApiKey: {
        aadAuthFailureMode: 'http401WithBearerChallenge'
      }
    }
  }
}

// ── Azure AI Services (Foundry Resource — new project model) ─

resource aiServices 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' = {
  name: 'ai-miq-${nameSuffix}'
  location: location
  kind: 'AIServices'
  sku: { name: 'S0' }
  identity: { type: 'SystemAssigned' }
  properties: {
    allowProjectManagement: true
    customSubDomainName: 'ai-miq-${nameSuffix}'
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: false
    networkAcls: {
      defaultAction: 'Allow'
      virtualNetworkRules: []
      ipRules: []
    }
  }
}

// ── AI Foundry Project (Agents V2 — no Hub) ──

resource aiProject 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' = {
  parent: aiServices
  name: 'miq-project-${nameSuffix}'
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {
    description: 'Microsoft IQ — Knowledge-grounded e-commerce agent project'
    displayName: 'Microsoft IQ'
  }
}

// ── GPT Model Deployment ─────────────────────

resource gptDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-04-01-preview' = {
  parent: aiServices
  name: 'gpt-4o-mini'
  sku: {
    name: 'GlobalStandard'
    capacity: 10
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-4o-mini'
      version: '2024-07-18'
    }
  }
}

// ══════════════════════════════════════════════
// RBAC — AI Search identity
// ══════════════════════════════════════════════

// Search → AI Services (Cognitive Services User)
resource searchToAiServicesRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(searchService.id, aiServices.id, cognitiveServicesUser)
  scope: aiServices
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesUser)
    principalId: searchService.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// Search → Storage (Blob Data Reader)
resource searchToStorageRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(searchService.id, storageAccount.id, storageBlobDataReader)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataReader)
    principalId: searchService.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// ══════════════════════════════════════════════
// RBAC — AI Services (Foundry resource) identity
// ══════════════════════════════════════════════

// AI Services → Storage (Blob Data Contributor)
resource aiServicesToStorageRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(aiServices.id, storageAccount.id, storageBlobDataContributor)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataContributor)
    principalId: aiServices.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// AI Services → AI Search (Index Data Reader)
resource aiServicesToSearchReaderRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(aiServices.id, searchService.id, searchIndexDataReader)
  scope: searchService
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', searchIndexDataReader)
    principalId: aiServices.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// AI Services → AI Search (Search Service Contributor)
resource aiServicesToSearchContribRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(aiServices.id, searchService.id, searchServiceContributor)
  scope: searchService
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', searchServiceContributor)
    principalId: aiServices.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// ══════════════════════════════════════════════
// RBAC — AI Project identity
// ══════════════════════════════════════════════

// Project → Storage (Blob Data Contributor)
resource projectToStorageRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(aiProject.id, storageAccount.id, storageBlobDataContributor)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataContributor)
    principalId: aiProject.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// Project → AI Search (Index Data Contributor)
resource projectToSearchDataRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(aiProject.id, searchService.id, searchIndexDataContributor)
  scope: searchService
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', searchIndexDataContributor)
    principalId: aiProject.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// Project → AI Search (Search Service Contributor)
resource projectToSearchContribRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(aiProject.id, searchService.id, searchServiceContributor)
  scope: searchService
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', searchServiceContributor)
    principalId: aiProject.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// Project → AI Services (Cognitive Services OpenAI User)
resource projectToAiServicesRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(aiProject.id, aiServices.id, cognitiveServicesOpenAIUser)
  scope: aiServices
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesOpenAIUser)
    principalId: aiProject.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// ══════════════════════════════════════════════
// RBAC — Deployer (current user) for data seeding
// ══════════════════════════════════════════════

// Deployer → Storage (Blob Data Contributor)
resource deployerToStorageRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(deployerPrincipalId, storageAccount.id, storageBlobDataContributor)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataContributor)
    principalId: deployerPrincipalId
    principalType: 'User'
  }
}

// Deployer → AI Search (Index Data Contributor)
resource deployerToSearchRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(deployerPrincipalId, searchService.id, searchIndexDataContributor)
  scope: searchService
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', searchIndexDataContributor)
    principalId: deployerPrincipalId
    principalType: 'User'
  }
}

// Deployer → AI Services (Cognitive Services User)
resource deployerToAiServicesRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(deployerPrincipalId, aiServices.id, cognitiveServicesUser)
  scope: aiServices
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesUser)
    principalId: deployerPrincipalId
    principalType: 'User'
  }
}

// ══════════════════════════════════════════════
// OUTPUTS
// ══════════════════════════════════════════════

output storageAccountName string = storageAccount.name
output storageContainerName string = containerName
output searchServiceName string = searchService.name
output searchServiceEndpoint string = 'https://${searchService.name}.search.windows.net'
output searchIndexName string = searchIndexName
output aiServicesEndpoint string = aiServices.properties.endpoint
output aiServicesName string = aiServices.name
output aiProjectName string = aiProject.name
output gptDeploymentName string = gptDeployment.name
