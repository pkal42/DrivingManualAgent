@description('Name for the Document Intelligence resource')
param documentIntelligenceName string

@description('Location for the Document Intelligence resource')
param location string = resourceGroup().location

@description('SKU for Document Intelligence')
@allowed([
  'F0'  // Free tier - 500 pages/month
  'S0'  // Standard tier
])
param sku string = 'S0'

@description('Tags to apply to the resource')
param tags object = {}

// Document Intelligence (formerly Form Recognizer) for PDF text extraction
// Replaces pypdf library with Azure-native service
resource documentIntelligence 'Microsoft.CognitiveServices/accounts@2024-04-01-preview' = {
  name: documentIntelligenceName
  location: location
  kind: 'FormRecognizer'  // Kind is still FormRecognizer for Document Intelligence
  sku: {
    name: sku
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    customSubDomainName: documentIntelligenceName
    networkAcls: {
      defaultAction: 'Allow'  // Allow public access for development
      virtualNetworkRules: []
      ipRules: []
    }
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: false  // Enable key-based auth for development (use managed identity in production)
  }
  tags: tags
}

// Outputs
output documentIntelligenceId string = documentIntelligence.id
output documentIntelligenceName string = documentIntelligence.name
output documentIntelligenceEndpoint string = documentIntelligence.properties.endpoint
output documentIntelligencePrincipalId string = documentIntelligence.identity.principalId
