class ConvertController < ApplicationController
  def create
    unless params[:file].present?
      render json: { error: "Missing file parameter" }, status: :bad_request
      return
    end

    file = params[:file]

    unless file.respond_to?(:tempfile) || file.respond_to?(:path)
      render json: { error: "Invalid file parameter" }, status: :bad_request
      return
    end

    file_path = file.respond_to?(:tempfile) ? file.tempfile.path : file.path

    unless File.exist?(file_path)
      render json: { error: "File not found" }, status: :bad_request
      return
    end

    output_file = Tempfile.new(["output", ".txt"])
    output_path = output_file.path
    output_file.close

    begin
      result = system("pdftotext", file_path, output_path)

      unless result
        render json: { error: "Conversion failed" }, status: :internal_server_error
        return
      end

      text = File.read(output_path, encoding: "utf-8")
      render plain: text, status: :ok
    rescue => e
      render json: { error: "Conversion failed: #{e.message}" }, status: :internal_server_error
    ensure
      File.delete(output_path) if File.exist?(output_path)
    end
  end
end