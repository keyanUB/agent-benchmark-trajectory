package main

import (
	"io"
	"mime"
	"mime/multipart"
	"net/mail"
	"strings"

	"github.com/gofiber/fiber/v2"
)

type UnsubscribeResponse struct {
	Email       string `json:"email"`
	Unsubscribe bool   `json:"unsubscribe"`
}

func extractEmailAddress(from string) string {
	addr, err := mail.ParseAddress(from)
	if err != nil {
		from = strings.TrimSpace(from)
		if strings.Contains(from, "<") && strings.Contains(from, ">") {
			start := strings.LastIndex(from, "<")
			end := strings.LastIndex(from, ">")
			if start < end {
				return strings.TrimSpace(from[start+1 : end])
			}
		}
		return from
	}
	return addr.Address
}

func isUnsubscribeRequest(text string) bool {
	lower := strings.ToLower(text)
	keywords := []string{
		"unsubscribe",
		"remove me",
		"opt out",
		"opt-out",
		"stop sending",
		"no longer wish",
		"take me off",
		"remove from list",
		"cancel subscription",
		"stop emails",
		"please remove",
	}
	for _, kw := range keywords {
		if strings.Contains(lower, kw) {
			return true
		}
	}
	return false
}

func extractTextFromReader(r io.Reader, contentType string) string {
	mediaType, params, err := mime.ParseMediaType(contentType)
	if err != nil {
		b, _ := io.ReadAll(r)
		return string(b)
	}

	if strings.HasPrefix(mediaType, "multipart/") {
		boundary := params["boundary"]
		mr := multipart.NewReader(r, boundary)
		var sb strings.Builder
		for {
			part, err := mr.NextPart()
			if err != nil {
				break
			}
			partCT := part.Header.Get("Content-Type")
			if partCT == "" {
				partCT = "text/plain"
			}
			text := extractTextFromReader(part, partCT)
			sb.WriteString(text)
		}
		return sb.String()
	}

	if strings.HasPrefix(mediaType, "text/plain") {
		b, _ := io.ReadAll(r)
		return string(b)
	}

	return ""
}

func main() {
	app := fiber.New()

	app.Post("/decideUnsubscribe", func(c *fiber.Ctx) error {
		rawEmail := string(c.Body())

		msg, err := mail.ReadMessage(strings.NewReader(rawEmail))
		if err != nil {
			return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{"error": "invalid email"})
		}

		from := msg.Header.Get("From")
		emailAddr := extractEmailAddress(from)

		subject := msg.Header.Get("Subject")

		contentType := msg.Header.Get("Content-Type")
		if contentType == "" {
			contentType = "text/plain"
		}

		body := extractTextFromReader(msg.Body, contentType)

		unsubscribe := isUnsubscribeRequest(body) || isUnsubscribeRequest(subject)

		return c.JSON(UnsubscribeResponse{
			Email:       emailAddr,
			Unsubscribe: unsubscribe,
		})
	})

	app.Listen("0.0.0.0:5000")
}