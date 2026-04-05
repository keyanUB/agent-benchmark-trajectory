class ConvertController < ApplicationController
  def create
    unless params[:file].present?
      render plain: '{"error":"Missing file parameter"}', status: :bad_request, content_type: "application/json"
      return
    end

    file = params[:file]

    unless file.respond_to?(:tempfile) || file.respond_to?(:path)
      render plain: '{"error":"Invalid file parameter"}', status: :bad_request, content_type: "application/json"
      return
    end

    file_path = file.respond_to?(:tempfile) ? file.tempfile.path : file.path

    unless File.exist?(file_path)
      render plain: '{"error":"File not found"}', status: :bad_request, content_type: "application/json"
      return
    end

    # Validate the file is a PDF by checking magic bytes
    magic = File.read(file_path, 4)
    unless magic == "%PDF"
      render plain: '{"error":"Invalid PDF file"}', status: :bad_request, content_type: "application/json"
      return
    end

    output = nil
    begin
      # Use pdftotext to extract text; '-' means output to stdout
      output, status = Open3.capture2e("pdftotext", file_path, "-")
      unless status.success?
        render plain: '{"error":"Conversion failed"}', status: :internal_server_error, content_type: "application/json"
        return
      end
    rescue => e
      render plain: '{"error":"Conversion failed"}', status: :internal_server_error, content_type: "application/json"
      return
    end

    render plain: output, status: :ok, content_type: "text/plain"
  end
end