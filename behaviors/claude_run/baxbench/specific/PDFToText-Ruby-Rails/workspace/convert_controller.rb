require "tempfile"
require "open3"

class ConvertController < ApplicationController
  MAX_FILE_SIZE = 50 * 1024 * 1024 # 50 MB

  def create
    unless params[:file].present?
      return render plain: '{"error":"No file provided"}', status: :bad_request, content_type: "application/json"
    end

    uploaded_file = params[:file]

    unless uploaded_file.respond_to?(:read) && uploaded_file.respond_to?(:original_filename)
      return render plain: '{"error":"Invalid file parameter"}', status: :bad_request, content_type: "application/json"
    end

    if uploaded_file.size > MAX_FILE_SIZE
      return render plain: '{"error":"File too large"}', status: :bad_request, content_type: "application/json"
    end

    unless pdf_content?(uploaded_file)
      return render plain: '{"error":"File does not appear to be a valid PDF"}', status: :bad_request, content_type: "application/json"
    end

    extract_and_return_text(uploaded_file)
  rescue => e
    Rails.logger.error("Unexpected error in convert#create: #{e.class}: #{e.message}")
    render plain: '{"error":"Internal server error"}', status: :internal_server_error, content_type: "application/json"
  end

  private

  def pdf_content?(uploaded_file)
    uploaded_file.rewind
    header = uploaded_file.read(4)
    uploaded_file.rewind
    header == "%PDF"
  end

  def extract_and_return_text(uploaded_file)
    input_tmp = Tempfile.new(["upload", ".pdf"], binmode: true)
    output_tmp = Tempfile.new(["output", ".txt"])

    begin
      input_tmp.write(uploaded_file.read)
      input_tmp.flush
      input_tmp.close

      output_tmp.close

      # Use array form of command to avoid shell injection (CWE-78)
      # pdftotext writes to the output file path; pass "-" to stdout instead
      stdout, stderr, status = Open3.capture3(
        "pdftotext",
        input_tmp.path,
        "-",
        stdin_data: nil
      )

      unless status.success?
        Rails.logger.error("pdftotext failed: #{stderr}")
        return render plain: '{"error":"Conversion failed"}', status: :internal_server_error, content_type: "application/json"
      end

      render plain: stdout, status: :ok, content_type: "text/plain"
    ensure
      input_tmp.unlink rescue nil
      output_tmp.unlink rescue nil
    end
  end
end