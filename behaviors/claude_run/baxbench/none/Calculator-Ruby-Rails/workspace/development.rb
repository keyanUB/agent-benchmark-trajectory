require "active_support/core_ext/integer/time"

Rails.application.configure do
  config.enable_reloading = true
  config.eager_load = false
  config.consider_all_requests_local = true
  config.server_timing = true

  config.active_record.migration_error = :page_load
  config.active_record.verbose_query_logs = true
  config.active_record.sqlite3_adapter_strict_strings_by_default = true

  config.action_controller.raise_on_missing_callback_actions = true
end