class ApplicationController < ActionController::API
  rescue_from StandardError, with: :handle_internal_error
  rescue_from ActiveRecord::RecordNotFound, with: :handle_not_found

  private

  def handle_not_found(e)
    render json: { error: "Not found" }, status: :not_found
  end

  def handle_internal_error(e)
    Rails.logger.error("Unhandled error: #{e.class}: #{e.message}\n#{e.backtrace&.first(5)&.join("\n")}")
    render json: { error: "Internal server error" }, status: :internal_server_error
  end
end