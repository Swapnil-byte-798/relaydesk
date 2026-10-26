CREATE TABLE IF NOT EXISTS workspaces (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS customers (
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    id TEXT NOT NULL,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    PRIMARY KEY (workspace_id, id)
);
CREATE TABLE IF NOT EXISTS orders (
    workspace_id TEXT NOT NULL,
    id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    item TEXT NOT NULL,
    amount_paise INTEGER NOT NULL CHECK (amount_paise > 0),
    status TEXT NOT NULL CHECK (status IN ('processing', 'shipped', 'delivered', 'cancelled', 'refunded')),
    delivered_at TEXT,
    estimated_at TEXT,
    tracking TEXT,
    PRIMARY KEY (workspace_id, id),
    FOREIGN KEY (workspace_id, customer_id) REFERENCES customers(workspace_id, id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS tickets (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'resolved', 'waiting_approval', 'needs_human')),
    intent TEXT NOT NULL DEFAULT 'unknown',
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    summary TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (workspace_id, id),
    FOREIGN KEY (workspace_id, customer_id) REFERENCES customers(workspace_id, id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    ticket_id TEXT NOT NULL,
    sequence_no INTEGER NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('customer', 'assistant', 'human')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (ticket_id, sequence_no),
    FOREIGN KEY (workspace_id, ticket_id) REFERENCES tickets(workspace_id, id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    ticket_id TEXT NOT NULL,
    request_key TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    response_json TEXT NOT NULL,
    mode TEXT NOT NULL,
    llm_calls INTEGER NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (workspace_id, request_key),
    FOREIGN KEY (workspace_id, ticket_id) REFERENCES tickets(workspace_id, id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    ticket_id TEXT NOT NULL,
    run_id TEXT,
    step INTEGER NOT NULL,
    node TEXT NOT NULL,
    detail TEXT NOT NULL,
    duration_ms INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id, ticket_id) REFERENCES tickets(workspace_id, id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS approvals (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    ticket_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    order_id TEXT NOT NULL,
    amount_paise INTEGER NOT NULL CHECK (amount_paise > 0),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    reason TEXT NOT NULL,
    policy_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    decided_at TEXT,
    decided_by TEXT,
    decision_note TEXT,
    UNIQUE (workspace_id, order_id),
    FOREIGN KEY (workspace_id, ticket_id) REFERENCES tickets(workspace_id, id) ON DELETE CASCADE,
    FOREIGN KEY (workspace_id, customer_id) REFERENCES customers(workspace_id, id),
    FOREIGN KEY (workspace_id, order_id) REFERENCES orders(workspace_id, id)
);
CREATE TABLE IF NOT EXISTS refunds (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    approval_id TEXT NOT NULL UNIQUE REFERENCES approvals(id),
    order_id TEXT NOT NULL,
    amount_paise INTEGER NOT NULL CHECK (amount_paise > 0),
    created_at TEXT NOT NULL,
    UNIQUE (workspace_id, order_id),
    FOREIGN KEY (workspace_id, order_id) REFERENCES orders(workspace_id, id)
);
CREATE TABLE IF NOT EXISTS ticket_approvals (
    workspace_id TEXT NOT NULL,
    ticket_id TEXT NOT NULL,
    approval_id TEXT NOT NULL REFERENCES approvals(id) ON DELETE CASCADE,
    PRIMARY KEY (ticket_id, approval_id),
    FOREIGN KEY (workspace_id, ticket_id) REFERENCES tickets(workspace_id, id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS orders_by_customer ON orders(workspace_id, customer_id);
CREATE INDEX IF NOT EXISTS tickets_by_status ON tickets(workspace_id, status, updated_at);
CREATE INDEX IF NOT EXISTS messages_by_ticket ON messages(workspace_id, ticket_id, sequence_no);
CREATE INDEX IF NOT EXISTS events_by_run ON events(workspace_id, run_id, step);
CREATE INDEX IF NOT EXISTS approvals_by_status ON approvals(workspace_id, status);
CREATE INDEX IF NOT EXISTS ticket_approvals_by_request ON ticket_approvals(workspace_id, approval_id);
