// ============================================================================
// Microsoft Foundry Project Module (Hubless Architecture)
// ============================================================================
// This module provisions the modern Microsoft Foundry resources using the
// account + project model introduced in 2025. Compared to the legacy
// hub/project pattern, this template:
// - Eliminates the intermediate Azure AI Foundry hub resource
// - Deploys a single Microsoft Foundry account (Cognitive Services resource)
//   with project management enabled
// - Creates a default project under that account for agent development
// - Enables managed identities and disables local auth for least-privilege
// - Exposes outputs compatible with downstream modules (model deployments,
//   RBAC, search skillsets)
// ============================================================================

targetScope = 'resourceGroup'

// ============================================================================
// Parameters
// ============================================================================

@description('Azure region where Microsoft Foundry resources will reside')
param location string

@description('Project name prefix used as part of resource naming')
param projectName string

@description('Short environment moniker (for example: dev, prod)')
param environmentName string

@description('Unique suffix to guarantee global uniqueness across accounts')
param uniqueSuffix string

@description('Tags applied to every resource for governance and cost tracking')
param tags object

// ============================================================================
// Variables
// ============================================================================

// Base label used for all Foundry identities. Lowercasing avoids subdomain
// validation issues and replacing underscores ensures DNS compatibility.
var baseLabel = replace(toLower('${projectName}-${environmentName}-${uniqueSuffix}'), '_', '-')

// Microsoft Foundry account (Cognitive Services account with AIServices kind)
var foundryAccountName = 'fdry-${baseLabel}'

// Foundry project resource name. Projects are scoped to the account and must
// remain globally unique within that account only, but we reuse the same suffix
// for clarity.
var foundryProjectName = 'proj-${baseLabel}'

// Human-friendly values surface inside the Foundry portal.
var projectDisplayName = 'DrivingManualAgent ${toUpper(environmentName)}'
var projectDescription = 'Microsoft Foundry project for DrivingManualAgent (${environmentName})'

// ============================================================================
// Microsoft Foundry Account (Cognitive Services)
// ============================================================================

resource aiFoundry 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: foundryAccountName
  location: location
  kind: 'AIServices'
  identity: {
    type: 'SystemAssigned' // Managed identity enables RBAC-secured data access
  }
  sku: {
    name: 'S0' // Pay-as-you-go tier supporting GPT-4o and embedding deployments
  }
  properties: {
    allowProjectManagement: true // Required for Foundry projects as child resources
    customSubDomainName: foundryAccountName // Enables API access via aiFoundry.properties.endpoint
    defaultProject: foundryProjectName // Route data plane calls to the default project
    disableLocalAuth: true // Enforce Azure AD based access; no shared keys
    publicNetworkAccess: 'Enabled' // Keep public endpoint (Private Link handled elsewhere)
    restrictOutboundNetworkAccess: false // Outbound egress governed by downstream network policy
    storedCompletionsDisabled: false // Allow persisted logs for analytics (can be toggled later)
    dynamicThrottlingEnabled: true // Helps smooth bursty workloads in dev environments
  }
  tags: tags
}

// ============================================================================
// Microsoft Foundry Project
// ============================================================================

resource aiProject 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: aiFoundry
  name: foundryProjectName
  location: location
  identity: {
    type: 'SystemAssigned' // Used for Search/Storage role assignments
  }
  properties: {
    displayName: projectDisplayName
    description: projectDescription
  }
  tags: tags
}

// ============================================================================
// Outputs
// ============================================================================

@description('Microsoft Foundry account (Cognitive Services) resource name')
output foundryAccountName string = aiFoundry.name

@description('HTTPS endpoint for Microsoft Foundry APIs (replaces legacy OpenAI endpoint)')
output foundryEndpoint string = aiFoundry.properties.endpoint

@description('Default Microsoft Foundry project name')
output projectName string = aiProject.name

@description('Managed identity principal ID for the Foundry project')
output projectPrincipalId string = aiProject.identity.principalId

@description('Display name assigned to the Foundry project in the portal')
output projectDisplayName string = projectDisplayName

// Backward-compatible aliases maintained for existing modules/tests consuming
// the earlier output contract. These map directly to the new Foundry resources.
@description('Legacy alias: Azure OpenAI service name (maps to Foundry account)')
output openAIName string = aiFoundry.name

@description('Legacy alias: Azure OpenAI endpoint (maps to Foundry endpoint)')
output openAIEndpoint string = aiFoundry.properties.endpoint
