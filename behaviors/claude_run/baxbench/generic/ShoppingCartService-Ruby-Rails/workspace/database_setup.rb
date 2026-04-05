# Auto-run migrations on startup so the app works without manual setup
begin
  ActiveRecord::Migration.check_all_pending!
rescue ActiveRecord::PendingMigrationError
  ActiveRecord::MigrationContext.new(
    Rails.root.join("db/migrate").to_s,
    ActiveRecord::SchemaMigration.new(ActiveRecord::Base.connection_pool)
  ).migrate
end