# Caddy + Tailscale Migration Design

**Date:** 2025-11-07
**Status:** Approved for Implementation
**Author:** Design conversation with user

## Overview

Replace socat with Caddy as the reverse proxy for IB Gateway API, adding Tailscale network isolation for enhanced security and monitoring capabilities.

## Goals

1. **Better monitoring:** Access logs, health checks, and metrics endpoints
2. **Tailscale-only access:** IB API accessible only from Tailscale network
3. **Minimal change:** Drop-in replacement approach, minimal disruption
4. **Simplified codebase:** Remove SSH tunnel complexity

## Non-Goals

- Application-layer TLS (relying on Tailscale's WireGuard encryption)
- Breaking changes to IB API protocol (remains plain TCP)
- Custom Caddy builds or plugins

## Security Model

**Network-layer security via Tailscale:**
- All traffic encrypted by WireGuard (industry-standard encryption)
- IB API only accessible from Tailscale network (not public internet)
- Network isolation at infrastructure level

**No application-layer TLS needed:**
- IB API clients connect via plain TCP (standard protocol)
- WireGuard provides encryption between client and container
- Simpler architecture, better compatibility

## Architecture

### Current Architecture (socat)

```
IB API (127.0.0.1:4001) → socat (0.0.0.0:4003) → Docker host (127.0.0.1:4001)
                                                      ↓
                                              Public/untrusted access possible
```

### New Architecture (Caddy + Tailscale)

```
IB API (127.0.0.1:4001) → Caddy (100.x.x.x:4003) → Tailscale network only
                           ↓
                    Health checks, metrics, logging

Trading client on Tailscale network
    ↓ WireGuard encrypted tunnel
    ↓ (ib-gateway.tailnet.ts.net:4003)
Caddy TCP reverse proxy
    ↓ Plain TCP
    ↓ (127.0.0.1:4001)
IB Gateway API
```

### Component Roles

| Component | Responsibility |
|-----------|---------------|
| **Tailscale** | Network connectivity, WireGuard encryption, device authentication |
| **Caddy** | TCP reverse proxy, access logging, health endpoints |
| **IB Gateway/TWS** | Trading API (unchanged) |

## Implementation Details

### 1. Package Installation

**Add to Dockerfiles:**
```dockerfile
# Install Caddy (official Debian package)
RUN curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | \
    gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
RUN curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | \
    tee /etc/apt/sources.list.d/caddy-stable.list
RUN apt-get update && apt-get install --no-install-recommends --yes caddy

# Install Tailscale (official installer)
RUN curl -fsSL https://tailscale.com/install.sh | sh
```

**Remove from Dockerfiles:**
- `socat` package (replaced by Caddy)
- `sshpass` package (SSH tunnels removed)
- `openssh-client` package (unless needed elsewhere)

### 2. Environment Variables

**New variables:**
```bash
# Tailscale configuration
TAILSCALE_AUTHKEY=""           # Required: Tailscale auth key (ephemeral/reusable)
TAILSCALE_HOSTNAME=""          # Optional: Custom hostname (default: container hostname)
TAILSCALE_TAGS=""              # Optional: ACL tags (e.g., "tag:ib-gateway")
TAILSCALE_EXTRA_ARGS=""        # Optional: Additional tailscale up arguments

# Caddy configuration
CADDY_ADMIN_DISABLED="true"    # Disable admin API (default: true)
CADDY_LOG_LEVEL="INFO"         # Log level: DEBUG, INFO, WARN, ERROR
ENABLE_HEALTH_CHECK="yes"      # Enable /health endpoint (default: yes)
```

**Removed variables:**
- All `SSH_*` variables (SSH_TUNNEL, SSH_OPTIONS, SSH_USER_TUNNEL, etc.)

**Unchanged variables:**
- `API_PORT` (still used for localhost binding: 4001/4002/7496/7497)
- `TRADING_MODE` (paper/live/both - still supported)
- Port mappings remain conceptually the same (4003/4004 for ib-gateway, 7498/7499 for TWS)

### 3. Caddy Configuration Template

**File:** `image-files/config/caddy/Caddyfile.tmpl`

```caddyfile
{
    admin off
    log {
        level ${CADDY_LOG_LEVEL}
    }
}

# Health check endpoint (localhost only)
:2019 {
    respond /health 200
    respond /ready 200
    respond /metrics 200
}

# IB API TCP proxy - binds to Tailscale IP only
${TAILSCALE_IP}:${PUBLISHED_PORT} {
    reverse_proxy 127.0.0.1:${LOCAL_PORT} {
        transport tcp
    }

    log {
        output file /var/log/caddy/access-${TRADING_MODE}.log
    }
}
```

**Template processing:**
1. Tailscale starts and obtains IP: `tailscale ip -4`
2. Export `TAILSCALE_IP` environment variable
3. Generate config: `envsubst < Caddyfile.tmpl > /etc/caddy/Caddyfile`
4. Start Caddy with generated config

### 4. Startup Sequence

**Integrated into `run.sh` / `run_tws.sh`:**

```bash
# 1. Start Tailscale daemon in background
tailscaled --tun=userspace-networking --state=/var/lib/tailscale/state.conf &
sleep 2

# 2. Bring up Tailscale network
tailscale up --authkey=${TAILSCALE_AUTHKEY} \
             --hostname=${TAILSCALE_HOSTNAME:-$(hostname)} \
             ${TAILSCALE_EXTRA_ARGS}

# 3. Wait for Tailscale IP and export it
while [ -z "$TAILSCALE_IP" ]; do
    TAILSCALE_IP=$(tailscale ip -4)
    [ -z "$TAILSCALE_IP" ] && sleep 1
done
export TAILSCALE_IP
echo "Tailscale IP: ${TAILSCALE_IP}"

# 4. Generate Caddyfile from template
envsubst < /path/to/Caddyfile.tmpl > /etc/caddy/Caddyfile

# 5. Start Caddy in background
caddy run --config /etc/caddy/Caddyfile &
sleep 1

# 6. Continue with existing startup (Xvfb, VNC, IB Gateway, etc.)
```

**Shutdown handling (update `stop_ibc()`):**
```bash
stop_ibc() {
    pkill caddy
    pkill tailscaled
    # ... existing cleanup for IBC, Xvfb, etc.
}
```

### 5. Dual Mode Support (`TRADING_MODE=both`)

When running both live and paper simultaneously:

**Generated Caddyfile:**
```caddyfile
# Live trading API
${TAILSCALE_IP}:4003 {
    reverse_proxy 127.0.0.1:4001
    log { output file /var/log/caddy/access-live.log }
}

# Paper trading API
${TAILSCALE_IP}:4004 {
    reverse_proxy 127.0.0.1:4002
    log { output file /var/log/caddy/access-paper.log }
}
```

**Advantages over socat:**
- Single Caddy process handles both (vs two socat processes)
- Separate log files for each mode
- Cleaner process management

## Code Changes

### Files to Modify

| File | Changes |
|------|---------|
| `Dockerfile.template` | Replace socat/ssh with Caddy/Tailscale installation |
| `Dockerfile.tws.template` | Same for TWS image |
| `image-files/scripts/common.sh` | Replace `port_forwarding()`, `start_socat()`, `start_ssh()` with `start_tailscale()`, `start_caddy()` |
| `image-files/scripts/run.sh` | Update `stop_ibc()` to kill Caddy/Tailscale |
| `image-files/tws-scripts/run_tws.sh` | Same for TWS |
| `docker-compose.yml` | Add Tailscale env vars, update volume mounts |
| `tws-docker-compose.yml` | Same for TWS |
| `README.md` | Update documentation for Caddy/Tailscale usage |
| `CLAUDE.md` | Update architecture description |

### Files to Delete

- `image-files/scripts/run_socat.sh` (entire file - 15 lines)
- `image-files/scripts/run_ssh.sh` (entire file)

### Files to Create

- `image-files/config/caddy/Caddyfile.tmpl` (new template)
- `docs/plans/2025-11-07-caddy-tailscale-migration-design.md` (this file)
- Migration guide in README or separate doc

## Docker Compose Changes

**Minimal changes to docker-compose.yml:**

```yaml
services:
  ib-gateway:
    # ... existing config
    environment:
      # Remove SSH variables
      # - SSH_TUNNEL=yes

      # Add Tailscale variables
      - TAILSCALE_AUTHKEY=${TAILSCALE_AUTHKEY}
      - TAILSCALE_HOSTNAME=ib-gateway
      - TAILSCALE_TAGS=tag:trading

    # Ports: can keep for backward compat, but primary access via Tailscale
    ports:
      - "127.0.0.1:4001:4003"  # Optional: local testing
      - "127.0.0.1:4002:4004"
      - "127.0.0.1:5900:5900"  # VNC unchanged

    # Add Tailscale state persistence
    volumes:
      - tailscale-state:/var/lib/tailscale
      - caddy-logs:/var/log/caddy
      # ... existing volumes

volumes:
  tailscale-state:
  caddy-logs:
```

**Port mapping notes:**
- Can keep existing port mappings for local testing/backward compatibility
- Primary access method: Tailscale network (`ib-gateway.tailnet.ts.net:4003`)
- Could remove port mappings entirely to enforce Tailscale-only access

## Client Connection Changes

**Before (localhost):**
```python
from ib_insync import IB
ib = IB()
ib.connect('127.0.0.1', 4001, clientId=1)
```

**After (Tailscale hostname):**
```python
from ib_insync import IB
ib = IB()
ib.connect('ib-gateway.your-tailnet.ts.net', 4003, clientId=1)
```

**Or via Tailscale IP:**
```python
ib.connect('100.64.x.x', 4003, clientId=1)  # Get IP from: docker exec <container> tailscale ip -4
```

**Connection security:**
- Plain TCP at application layer (standard IB API protocol)
- WireGuard encryption at network layer (Tailscale)
- Only accessible from devices on Tailscale network

## Testing Plan

### Development Testing

1. **Build container:**
   ```bash
   docker compose build
   ```

2. **Configure Tailscale:**
   - Obtain auth key from Tailscale admin console
   - Set in `.env`: `TAILSCALE_AUTHKEY=tskey-auth-xxx`

3. **Start container:**
   ```bash
   docker compose up
   ```

4. **Verify Tailscale:**
   ```bash
   docker exec <container> tailscale status
   docker exec <container> tailscale ip -4
   ```

5. **Test API access from Tailscale device:**
   - Connect trading app to Tailscale IP:4003
   - Verify successful connection

6. **Check health endpoint:**
   ```bash
   docker exec <container> curl http://localhost:2019/health
   # Expected: "OK" with 200 status
   ```

7. **Review logs:**
   ```bash
   docker exec <container> cat /var/log/caddy/access-live.log
   ```

### Dual Mode Testing

1. Set `TRADING_MODE=both` with credentials
2. Verify both ports accessible: `<tailscale-ip>:4003` and `<tailscale-ip>:4004`
3. Confirm separate log files: `access-live.log` and `access-paper.log`

### Multi-arch Testing

- Test both amd64 and arm64 builds in CI
- Verify Tailscale works on both architectures

## Monitoring & Observability

**Health checks:**
- `GET http://localhost:2019/health` - Returns 200 OK
- `GET http://localhost:2019/ready` - Returns 200 OK
- Can integrate with Docker HEALTHCHECK directive

**Access logs:**
- Location: `/var/log/caddy/access-${TRADING_MODE}.log`
- Contains: Client IP, connection timestamps, bytes transferred
- Useful for debugging connection issues

**Tailscale monitoring:**
- `tailscale status` - Show connected devices
- `tailscale netcheck` - Network connectivity diagnostics
- Tailscale admin console - Online/offline status

## Migration Impact

### Breaking Changes

This is a **breaking change** for users:

1. **Tailscale required:** Users must set up Tailscale and obtain auth key
2. **Connection string changes:** Clients connect to Tailscale hostname/IP, not localhost
3. **Environment variables:** Must set `TAILSCALE_AUTHKEY` (and optionally hostname)
4. **SSH tunnels removed:** Users relying on SSH_TUNNEL must migrate to Tailscale

### Migration Path

**For existing users:**

1. Install Tailscale on trading application host
2. Obtain Tailscale auth key (preferably ephemeral + reusable)
3. Update docker-compose.yml with Tailscale env vars
4. Rebuild container with new image
5. Update trading application connection strings
6. Remove SSH tunnel configuration if present

**Backward compatibility:**
- Port mappings can remain for local testing
- Could provide "migration mode" that runs both socat and Caddy temporarily
- Not recommended: adds complexity

## Alternatives Considered

### 1. Keep socat, add Tailscale separately
- **Pro:** Non-breaking change, gradual migration
- **Con:** Doesn't achieve monitoring goal, adds complexity

### 2. Application-layer TLS (stunnel)
- **Pro:** Defense-in-depth security
- **Con:** IB API clients don't support TLS, requires wrapper/custom code
- **Decision:** Rejected - WireGuard encryption is sufficient

### 3. Sidecar container for Tailscale
- **Pro:** More modular, easier to update components
- **Con:** More complex docker-compose, networking challenges
- **Decision:** Rejected - integrated approach is simpler

### 4. Custom Caddy build with layer4 plugin
- **Pro:** More Caddy features available
- **Con:** Adds build time, unnecessary for basic TCP proxying
- **Decision:** Rejected - standard Caddy is sufficient

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Tailscale daemon fails to start | Add startup health checks, clear error messages |
| Tailscale auth key expires | Use reusable keys, document key rotation process |
| Performance degradation | Benchmark Caddy vs socat, WireGuard is highly optimized |
| User migration challenges | Provide detailed migration guide, example configs |
| Multi-arch compatibility | Test both amd64/arm64 in CI before release |

## Success Criteria

1. ✅ IB Gateway API accessible only from Tailscale network
2. ✅ Access logs capture connection details
3. ✅ Health endpoints functional
4. ✅ Dual mode (live + paper) works correctly
5. ✅ No performance degradation vs socat
6. ✅ Documentation complete (README, migration guide)
7. ✅ CI builds succeed for both images and architectures

## Future Enhancements

**Potential follow-ups (not in scope):**
- Prometheus metrics exporter for Caddy
- Alerting on connection failures
- Tailscale ACL examples for IB Gateway
- Rate limiting on API connections
- Connection pooling/limiting

## References

- Caddy documentation: https://caddyserver.com/docs/
- Tailscale documentation: https://tailscale.com/kb/
- IB API documentation: https://interactivebrokers.github.io/tws-api/
- Docker userspace networking: https://tailscale.com/kb/1112/userspace-networking/
