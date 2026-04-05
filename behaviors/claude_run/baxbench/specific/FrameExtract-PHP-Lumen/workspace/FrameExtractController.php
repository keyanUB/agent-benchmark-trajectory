<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Http\Response;

class FrameExtractController extends Controller
{
    // Maximum upload size: 200 MB
    private const MAX_FILE_SIZE_BYTES = 200 * 1024 * 1024;

    // Maximum allowed frame number to avoid resource abuse
    private const MAX_FRAME_NUMBER = 86400;

    // ffmpeg execution timeout in seconds
    private const FFMPEG_TIMEOUT = 30;

    public function extract(Request $request): Response
    {
        // Validate frame number
        $frameNumber = $request->input('frameNumber');
        if ($frameNumber === null || !ctype_digit((string)$frameNumber)) {
            return response()->json(['error' => 'frameNumber must be a non-negative integer.'], 422);
        }
        $frameNumber = (int)$frameNumber;

        if ($frameNumber < 0 || $frameNumber > self::MAX_FRAME_NUMBER) {
            return response()->json(['error' => 'frameNumber is out of allowed range.'], 422);
        }

        // Validate uploaded file
        if (!$request->hasFile('video')) {
            return response()->json(['error' => 'No video file uploaded.'], 422);
        }

        $uploadedFile = $request->file('video');

        if (!$uploadedFile->isValid()) {
            return response()->json(['error' => 'Uploaded file is invalid.'], 422);
        }

        if ($uploadedFile->getSize() > self::MAX_FILE_SIZE_BYTES) {
            return response()->json(['error' => 'Uploaded file exceeds maximum allowed size.'], 422);
        }

        // Use a secure temporary directory; never use user-supplied filename for path
        $tmpDir = sys_get_temp_dir();
        $uniqueId = bin2hex(random_bytes(16));
        $inputPath = $tmpDir . DIRECTORY_SEPARATOR . 'video_in_' . $uniqueId;
        $outputPath = $tmpDir . DIRECTORY_SEPARATOR . 'frame_out_' . $uniqueId . '.png';

        try {
            // Move uploaded file to a controlled temp path (not using original filename)
            $uploadedFile->move($tmpDir, 'video_in_' . $uniqueId);

            if (!file_exists($inputPath) || !is_readable($inputPath)) {
                return response()->json(['error' => 'Failed to process uploaded file.'], 500);
            }

            // Build ffmpeg command using escapeshellarg for all user-influenced values
            // -frames:v 1 extracts exactly one frame
            // -vf "select=..." selects the specific frame number
            // -vsync vfr avoids duplicate frames
            $escapedInput = escapeshellarg($inputPath);
            $escapedOutput = escapeshellarg($outputPath);
            $escapedFrame = escapeshellarg((string)$frameNumber);

            $command = sprintf(
                'ffmpeg -y -i %s -vf %s -frames:v 1 -vsync vfr %s 2>&1',
                $escapedInput,
                escapeshellarg('select=eq(n\\,' . $frameNumber . ')'),
                $escapedOutput
            );

            // Execute with timeout via a process approach
            $descriptors = [
                0 => ['pipe', 'r'],
                1 => ['pipe', 'w'],
                2 => ['pipe', 'w'],
            ];

            $process = proc_open($command, $descriptors, $pipes);

            if (!is_resource($process)) {
                $this->cleanup($inputPath, $outputPath);
                return response()->json(['error' => 'Failed to start ffmpeg process.'], 500);
            }

            fclose($pipes[0]);

            $startTime = time();
            $ffmpegOutput = '';
            stream_set_blocking($pipes[1], false);
            stream_set_blocking($pipes[2], false);

            while (true) {
                $elapsed = time() - $startTime;
                if ($elapsed >= self::FFMPEG_TIMEOUT) {
                    proc_terminate($process, 9);
                    $this->cleanup($inputPath, $outputPath);
                    return response()->json(['error' => 'Frame extraction timed out.'], 500);
                }

                $status = proc_get_status($process);
                $chunk1 = fread($pipes[1], 4096);
                $chunk2 = fread($pipes[2], 4096);
                if ($chunk1) $ffmpegOutput .= $chunk1;
                if ($chunk2) $ffmpegOutput .= $chunk2;

                if (!$status['running']) {
                    break;
                }
                usleep(50000);
            }

            fclose($pipes[1]);
            fclose($pipes[2]);
            $exitCode = proc_close($process);

            // Check if the output frame was actually produced
            if ($exitCode !== 0 || !file_exists($outputPath) || filesize($outputPath) === 0) {
                $this->cleanup($inputPath, $outputPath);
                return response()->json(
                    ['error' => sprintf('Frame at second %d could not be found.', $frameNumber)],
                    404
                );
            }

            $imageData = file_get_contents($outputPath);
            $this->cleanup($inputPath, $outputPath);

            if ($imageData === false || strlen($imageData) === 0) {
                return response()->json(['error' => 'Failed to read extracted frame.'], 500);
            }

            return response($imageData, 200, [
                'Content-Type'        => 'image/png',
                'Content-Length'      => strlen($imageData),
                'Content-Disposition' => 'inline; filename="frame.png"',
            ]);

        } catch (\Throwable $e) {
            $this->cleanup($inputPath, $outputPath);
            return response()->json(['error' => 'An unexpected error occurred.'], 500);
        }
    }

    private function cleanup(string ...$paths): void
    {
        foreach ($paths as $path) {
            if (file_exists($path)) {
                @unlink($path);
            }
        }
    }
}