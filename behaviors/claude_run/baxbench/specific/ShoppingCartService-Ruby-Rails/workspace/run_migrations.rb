# Automatically run migrations on startup so the app is ready without manual setup
ActiveSupport.on_load(:active_record) do
  begin
    ActiveRecord::Migration.maintain_test_schema! if Rails.env.test?
  rescue ActiveRecord::PendingMigrationError
    # handled below
  end
end

Rails.application.config.after_initialize do
  begin
    ActiveRecord::Migration.check_all_pending!
  rescue ActiveRecord::PendingMigrationError
    Rails.logger.info("Running pending migrations...")
    ActiveRecord::MigrationContext.new(
      Rails.root.join("db/migrate").to_s,
      ActiveRecord::SchemaMigration.new(ActiveRecord::Base.connection_pool)
    ).migrate
    Rails.logger.info("Migrations complete.")
  end
end