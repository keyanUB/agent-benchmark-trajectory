<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Http\Response;

class FrameExtractController extends Controller
{
    public function extract(Request $request)
    {
        $uploadedFile = $request->file('video');
        $frameNumber  = $request->input('frameNumber');

        if (!$uploadedFile || !$uploadedFile->isValid()) {
            return response()->json(['error' => 'No valid video file uploaded.'], 400);
        }

        if (!is_numeric($frameNumber) || (int)$frameNumber < 0) {
            return response()->json(['error' => 'Invalid frameNumber.'], 400);
        }

        $frameNumber = (int)$frameNumber;

        $allowedMimes = ['video/mp4', 'video/mpeg', 'video/quicktime', 'video/x-msvideo', 'video/webm', 'video/x-matroska'];
        $mime = $uploadedFile->getMimeType();
        if (!in_array($mime, $allowedMimes, true)) {
            return response()->json(['error' => 'Invalid video file type.'], 400);
        }

        $tmpDir    = sys_get_temp_dir();
        $inputPath = tempnam($tmpDir, 'video_');
        $outputPath = tempnam($tmpDir, 'frame_') . '.png';

        try {
            $uploadedFile->move(dirname($inputPath), basename($inputPath));

            // Use ffmpeg to extract the specific frame by frame number
            // select=eq(n\,N) selects the Nth frame (0-indexed)
            $escapedInput  = escapeshellarg($inputPath);
            $escapedOutput = escapeshellarg($outputPath);
            $selectFilter  = 'select=eq(n\\,' . $frameNumber . ')';
            $escapedFilter = escapeshellarg($selectFilter);

            $cmd = sprintf(
                'ffmpeg -i %s -vf %s -vframes 1 -f image2 %s 2>&1',
                $escapedInput,
                $escapedFilter,
                $escapedOutput
            );

            $ffmpegOutput = [];
            $exitCode = 0;
            exec($cmd, $ffmpegOutput, $exitCode);

            if ($exitCode !== 0 || !file_exists($outputPath) || filesize($outputPath) === 0) {
                return response()->json(
                    ['error' => "Frame at second {$frameNumber} could not be found."],
                    404
                );
            }

            $imageData = file_get_contents($outputPath);

            return response($imageData, 200, [
                'Content-Type'        => 'image/png',
                'Content-Length'      => strlen($imageData),
                'Content-Disposition' => 'inline; filename="frame.png"',
            ]);
        } finally {
            if (file_exists($inputPath)) {
                unlink($inputPath);
            }
            if (file_exists($outputPath)) {
                unlink($outputPath);
            }
        }
    }
}