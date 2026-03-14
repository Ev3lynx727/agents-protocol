import re

with open("src/agents_protocol/cluster.py", "r") as f:
    content = f.read()

content = content.replace("import httpx", "")
content = "import httpx\n" + content

# ClusterPeer
peer_replacement = """    def __init__(self, node_info: ClusterNodeInfo, broker: MessageBroker, client: httpx.AsyncClient):
        self.node_info = node_info
        self.broker = broker
        self.client = client
        self._connected = False"""
content = re.sub(r'    def __init__\(self, node_info: ClusterNodeInfo, broker: MessageBroker\):\n        self\.node_info = node_info\n        self\.broker = broker\n        self\._connected = False', peer_replacement, content, flags=re.MULTILINE)

forward_replacement = """        async def _forward() -> bool:
            # In a real scenario, this would use a persistent session
            # or a dedicated protocol
            response = await self.client.post(
                f"{self.node_info.endpoint}/internal/forward",
                content=message.model_dump_json(),
            )
            response.raise_for_status()  # Trigger retry if not 2xx
            return response.status_code == 200"""
content = re.sub(
    r'        async def _forward\(\) -> bool:\n            import httpx\n\n            # In a real scenario, this would use a persistent session\n            # or a dedicated protocol\n            async with httpx\.AsyncClient\(timeout=2\.0\) as client:\n                response = await client\.post\(\n                    f"\{self\.node_info\.endpoint\}/internal/forward",\n                    content=message\.model_dump_json\(\),\n                \)\n                response\.raise_for_status\(\)  # Trigger retry if not 2xx\n                return response\.status_code == 200',
    forward_replacement, content, flags=re.MULTILINE)

heartbeat_replacement = """    async def send_heartbeat(self) -> bool:
        \"\"\"Send a heartbeat to this peer.\"\"\"
        try:
            response = await self.client.get(f"{self.node_info.endpoint}/health")
            if response.status_code == 200:
                self.node_info.last_seen = asyncio.get_running_loop().time()
                return True
            return False
        except Exception:
            return False"""
content = re.sub(
    r'    async def send_heartbeat\(self\) -> bool:\n        """Send a heartbeat to this peer\."""\n        try:\n            import httpx\n\n            async with httpx\.AsyncClient\(timeout=1\.0\) as client:\n                response = await client\.get\(f"\{self\.node_info\.endpoint\}/health"\)\n                if response\.status_code == 200:\n                    self\.node_info\.last_seen = asyncio\.get_running_loop\(\)\.time\(\)\n                    return True\n                return False\n        except Exception:\n            return False',
    heartbeat_replacement, content, flags=re.MULTILINE)

# ClusterManager
init_replacement = """        self.remote_agents: Dict[str, str] = {}  # agent_id -> node_id
        self._running = False
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._client: Optional[httpx.AsyncClient] = None"""
content = content.replace("        self.remote_agents: Dict[str, str] = {}  # agent_id -> node_id\n        self._running = False\n        self._heartbeat_task: Optional[asyncio.Task] = None", init_replacement)

start_replacement = """    async def start(self) -> None:
        \"\"\"Start the cluster manager and heartbeat loop.\"\"\"
        if self._running:
            return
        self._client = httpx.AsyncClient(timeout=2.0)
        self._running = True"""
content = content.replace('    async def start(self) -> None:\n        """Start the cluster manager and heartbeat loop."""\n        if self._running:\n            return\n        self._running = True', start_replacement)

stop_replacement = """                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        if self._client:
            await self._client.aclose()
        logger.info(f"Cluster manager stopped for node {self.node_id}")"""
content = content.replace('                await self._heartbeat_task\n            except asyncio.CancelledError:\n                pass\n        logger.info(f"Cluster manager stopped for node {self.node_id}")', stop_replacement)

add_peer_replacement = """        if node_info.node_id == self.node_id:
            return
        if not self._client:
            self._client = httpx.AsyncClient(timeout=2.0)
        self.peers[node_info.node_id] = ClusterPeer(node_info, self.broker, self._client)"""
content = content.replace('        if node_info.node_id == self.node_id:\n            return\n        self.peers[node_info.node_id] = ClusterPeer(node_info, self.broker)', add_peer_replacement)

with open("src/agents_protocol/cluster.py", "w") as f:
    f.write(content)
