-- app/redis/scripts/token_bucket.lua

-- KEYS[1] = rate limit key
-- ARGV[1] = capacity
-- ARGV[2] = refill_rate
-- ARGV[3] = current_time
-- ARGV[4] = requested_tokens
-- ARGV[5] = ttl

local key = KEYS[1]

local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local requested = tonumber(ARGV[4])
local ttl = tonumber(ARGV[5])

local data = redis.call("HMGET", key, "tokens", "last_refill")

local tokens = tonumber(data[1])
local last_refill = tonumber(data[2])

if tokens == nil then tokens = capacity end
if last_refill == nil then last_refill = now end

local elapsed = math.max(0, now - last_refill)
local refill = elapsed * refill_rate
tokens = math.min(capacity, tokens + refill)

local allowed = 0
local retry_after = 0

if tokens >= requested then
    allowed = 1
    tokens = tokens - requested
else
    local needed = requested - tokens
    retry_after = needed / refill_rate
end

redis.call("HMSET", key,
    "tokens", tokens,
    "last_refill", now
)

redis.call("EXPIRE", key, ttl)

return { allowed, tokens, retry_after }