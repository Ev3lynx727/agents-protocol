# Clustering and Distribution

Scale your agent system across multiple nodes using the clustering features.

## 1. Cluster Manager

Coordinates peer-to-peer communication between different broker instances.

### Setup

```python
from agents_protocol.cluster import ClusterManager

cluster_manager = ClusterManager(node_id="node-1", host="10.0.0.1", port=8080)
broker = MessageBroker(cluster_manager=cluster_manager)

# Add peers (other nodes)
await cluster_manager.add_peer("node-2", "10.0.0.2:8080")
```

## 2. Automatic Health Checks

The `ClusterManager` monitors peer health via heartbeats and automatically prunes stale or disconnected nodes.

## 3. Distributed Message Routing

When sending a message to an agent ID not found locally, the broker automatically:

1. Queries the `ClusterManager` for the agent's location.
2. Forwards the message to the appropriate peer node.
3. The remote node delivers the message to the local agent.

## 4. Resilience in Clusters

Message forwarding between nodes is protected by **Circuit Breakers** and **Retry Policies** to ensure system stability during partial outages.
