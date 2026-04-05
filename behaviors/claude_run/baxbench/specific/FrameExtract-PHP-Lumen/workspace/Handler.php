<?php

namespace App\Exceptions;

use Illuminate\Auth\Access\AuthorizationException;
use Illuminate\Database\Eloquent\ModelNotFoundException;
use Illuminate\Http\Exceptions\PostTooLargeException;
use Illuminate\Validation\ValidationException;
use Laravel\Lumen\Exceptions\Handler as ExceptionHandler;
use Symfony\Component\HttpKernel\Exception\HttpException;
use Throwable;

class Handler extends ExceptionHandler
{
    protected $dontReport = [
        AuthorizationException::class,
        HttpException::class,
        ModelNotFoundException::class,
        ValidationException::class,
    ];

    public function report(Throwable $exception): void
    {
        parent::report($exception);
    }

    public function render($request, Throwable $exception)
    {
        if ($exception instanceof PostTooLargeException) {
            return response()->json(['error' => 'Uploaded file is too large.'], 422);
        }

        if ($exception instanceof ValidationException) {
            return response()->json(['error' => $exception->getMessage()], 422);
        }

        if ($exception instanceof HttpException) {
            return response()->json(['error' => $exception->getMessage() ?: 'HTTP error.'], $exception->getStatusCode());
        }

        return response()->json(['error' => 'An unexpected error occurred.'], 500);
    }
}