export interface TokenResponse {
  access_token: string;
  token_type?: string;
  refresh_token?: string | null;
}

export interface User {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  is_admin: boolean;
  email_verified_at: string | null;
  created_at: string;
}

export interface Organization {
  id: number;
  name: string;
  email: string;
  settings: Record<string, unknown>;
  created_at: string;
}

export interface Plan {
  slug: string;
  name: string;
  price_cents: number;
  currency: string;
  product_limit: number;
  checks_per_day: number;
  history_days: number;
  features: string[];
}

export interface Subscription {
  id: number;
  status: string;
  current_period_end: string | null;
  trial_ends_at: string | null;
  plan: Plan | null;
  plan_slug: string | null;
}

export interface Competitor {
  id: number;
  name: string;
  domain: string;
  products_count: number;
}

export interface Product {
  id: number;
  url: string;
  name: string;
  category: string | null;
  sku: string | null;
  check_interval_hours: number | null;
  is_active: boolean;
  is_scraper_enabled: boolean;
  last_price: number | null;
  previous_price: number | null;
  currency: string | null;
  last_availability: string | null;
  seen_promotion: boolean;
  last_scrape_status: string;
  last_scrape_error: string | null;
  last_checked_at: string | null;
  next_check_at: string | null;
  created_at: string;
  variation_pct: number | null;
  variation_abs: number | null;
  competitor_id: number | null;
  competitor_name: string | null;
  own_price: number | null;
  own_currency: string | null;
  own_name: string | null;
  stats: Record<string, unknown>;
}

export interface Snapshot {
  id: number;
  scraped_at: string;
  price: number | null;
  original_price: string | null;
  currency: string | null;
  previous_price: number | null;
  availability: string | null;
  in_promotion: boolean;
  stock_quantity: number | null;
  shipping_cost: number | null;
  product_name: string | null;
  ean: string | null;
}

export interface History {
  product: Product;
  snapshots: Snapshot[];
  own_prices: { price: number; currency: string; at: string }[];
}

export interface ChangeEvent {
  id: number;
  event_type: string;
  importance: string;
  title: string;
  old_state: Record<string, unknown> | null;
  new_state: Record<string, unknown> | null;
  created_at: string;
  product_id: number;
  product_name: string | null;
  product_url: string | null;
  competitor_name: string | null;
}

export interface Dashboard {
  products_count: number;
  active_products: number;
  changes_today: number;
  price_drops_today: number;
  price_rises_today: number;
  out_of_stock_today: number;
  scrape_errors: number;
  checks_today: number;
  plan: Subscription | null;
  recent_changes: ChangeEvent[];
  product_preview: Product[];
}

export interface NotificationRow {
  id: number;
  channel: string;
  status: string;
  subject: string | null;
  created_at: string;
  event_type: string | null;
  product_name: string | null;
  read: boolean;
}

export interface CsvPreview {
  valid_rows: Record<string, string>[];
  invalid_rows: Record<string, string>[];
  errors: string[];
}

export interface CsvResult {
  imported: number;
  skipped: number;
  errors: string[];
}

export interface AdminStats {
  users: number;
  organizations: number;
  products: number;
  subscriptions: Record<string, number>;
  snapshots: number;
  change_events: number;
  scrape_errors: number;
  queued_jobs: number;
  failed_jobs: number;
  domains: { domain: string; scrapes: number; errors: number }[];
  recent_failures: {
    id: number;
    product_id: number;
    url: string;
    error: string | null;
    finished_at: string;
    http_status: number | null;
  }[];
}

export interface OrgAdmin {
  id: number;
  name: string;
  email: string;
  created_at: string;
  products_count: number;
  users_count: number;
  plan_slug: string | null;
}

export interface DomainState {
  id: number;
  name: string;
  disabled: boolean;
  disabled_reason: string | null;
}

export interface ProductSearchResult {
  domain: string;
  label: string;
  name: string;
  url: string;
  price: number | null;
  currency: string | null;
  availability: string | null;
  image_url: string | null;
  tracked: boolean;
}

export interface MerchantSearchStatus {
  domain: string;
  label: string;
  ok: boolean;
  error: string | null;
}

export interface ProductSearchResponse {
  query: string;
  merchants: MerchantSearchStatus[];
  results: ProductSearchResult[];
}