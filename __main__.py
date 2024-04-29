import pulumi
from pulumi_azure_native import resources, containerservice
from pulumi_azure_native.containerservice import ManagedCluster, ManagedClusterServicePrincipalProfile
from pulumi_azure_native.resources import ResourceGroup
from pulumi_kubernetes import Provider
from pulumi_kubernetes.helm.v3 import Chart, ChartOpts

# Create a new resource group
resource_group = ResourceGroup('rg')

# Create an AKS cluster
aks_cluster = ManagedCluster(
    'aksCluster',
    resource_group_name=resource_group.name,
    agent_pool_profiles=[{
        'count': 3,
        'max_pods': 110,
        'mode': 'System',
        'name': 'agentpool',
        'os_type': 'Linux',
        'vm_size': 'Standard_DS2_v2',
    }],
    dns_prefix='aksCluster',
    linux_profile={
        'admin_username': 'adminuser',
        'ssh': {
            'publicKeys': [{
                'keyData': 'ssh-rsa AAAAB3Nza...'
            }]
        }
    },
    service_principal_profile=ManagedClusterServicePrincipalProfile(
        client_id='your-client-id',
        secret='your-client-secret',
    )
)

# Create a Kubernetes provider instance using the kubeconfig from the AKS cluster
k8s_provider = Provider(
    'k8sProvider',
    kubeconfig=aks_cluster.kube_config_raw,
)

# Deploy an NGINX Helm chart using the Kubernetes provider
nginx_chart = Chart(
    'nginx',
    ChartOpts(
        chart='nginx',
        version='9.3.7',  # Make sure to check for the latest version
        fetch_opts={
            'repo': 'https://charts.bitnami.com/bitnami',
        },
    ),
    opts=pulumi.ResourceOptions(provider=k8s_provider)
)

# Install Karpenter
karpenter_chart = Chart(
    "karpenter",
    ChartOpts(
        chart="karpenter",
        version="0.11.1",  # Check for the latest version from Karpenter's Helm repository
        namespace="karpenter",
        fetch_opts={
            "repo": "https://charts.karpenter.sh",
        },
        values={
            "clusterName": aks_cluster.name,
            "clusterEndpoint": aks_cluster.private_fqdn,
        }
    ),
    opts=pulumi.ResourceOptions(provider=k8s_provider, depends_on=[nginx_chart])
)

# Export the kubeconfig and the public IP of the NGINX service
pulumi.export('kubeconfig', aks_cluster.kube_config_raw)
nginx_service = nginx_chart.get_resource('v1/Service', 'nginx-nginx')
pulumi.export('nginx_ip', nginx_service.status.apply(lambda status: status.load_balancer.ingress[0].ip))

# Export Karpenter chart status
pulumi.export('karpenter_chart_status', karpenter_chart.status)