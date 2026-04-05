begin
  ActiveRecord::Base.connection.execute("SELECT 1")
rescue ActiveRecord::NoDatabaseError
  ActiveRecord::Tasks::DatabaseTasks.create_current
end

begin
  if ActiveRecord::Base.connection.migration_context.needs_migration?
    ActiveRecord::MigrationContext.new(
      Rails.root.join("db/migrate"),
      ActiveRecord::SchemaMigration
    ).migrate
  end
rescue => e
  Rails.logger.warn "Migration check failed: #{e.message}"
end