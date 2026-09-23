/**
 * KeyValue.tsx — key-value metadata rows.
 * DOC 3 Web App Shell: shared/ui — KeyValue
 */

import React from "react";

interface KVItem {
  key: string;
  value: React.ReactNode;
  id?: string;
}

interface KeyValueProps {
  items: KVItem[];
  className?: string;
}

export function KeyValue({ items, className = "" }: KeyValueProps) {
  return (
    <dl className={`nk-kv ${className}`}>
      {items.map((item, i) => (
        <div key={item.id ?? item.key ?? i} className="nk-kv__row">
          <dt className="nk-kv__key">{item.key}</dt>
          <dd className="nk-kv__value">{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}
