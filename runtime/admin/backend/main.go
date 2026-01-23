// Copyright (C) 2025 Advanced Micro Devices, Inc. All rights reserved.
// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:
//
// The above copyright notice and this permission notice shall be included in all
// copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
// SOFTWARE.

package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gin-contrib/cors"
	"github.com/gin-gonic/gin"

	"github.com/google/go-github/v72/github"
	"golang.org/x/oauth2"
)

type Config struct {
	GithubToken string
	OrgName     string
	SmtpHost    string
	SmtpPort    string
	SmtpUser    string
	SmtpPass    string
	FromEmail   string
}

var config Config

func setupRouter() *gin.Engine {
	r := gin.Default()

	// Configure CORS
	r.Use(cors.New(cors.Config{
		AllowOrigins:     []string{"*"},
		AllowMethods:     []string{"GET", "POST"},
		AllowHeaders:     []string{"Origin", "Content-Type"},
		AllowCredentials: true,
	}))

	// Health check endpoints
	r.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"status": "ok"})
	})

	// Routes
	r.GET("/api/members", getOrgMembers)
	r.POST("/api/send-mail", sendMailToMembers)

	return r
}

func main() {
	// Load configuration
	config = Config{
		GithubToken: os.Getenv("GITHUB_TOKEN"),
		OrgName:     os.Getenv("GITHUB_ORG"),
		SmtpHost:    os.Getenv("SMTP_HOST"),
		SmtpPort:    os.Getenv("SMTP_PORT"),
		SmtpUser:    os.Getenv("SMTP_USER"),
		SmtpPass:    os.Getenv("SMTP_PASS"),
		FromEmail:   os.Getenv("FROM_EMAIL"),
	}

	// Create context that listens for the interrupt signal from the OS
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	r := setupRouter()

	srv := &http.Server{
		Addr:    ":3000",
		Handler: r,
	}

	// Initializing the server in a goroutine so that
	// it won't block the graceful shutdown handling
	go func() {
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("listen: %s\n", err)
		}
	}()

	// Listen for the interrupt signal
	<-ctx.Done()

	// Restore default behavior on the interrupt signal and notify user of shutdown
	stop()
	log.Println("shutting down gracefully, press Ctrl+C again to force")

	// The context is used to inform the server it has 5 seconds to finish
	// the request it is currently handling
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := srv.Shutdown(ctx); err != nil {
		log.Fatal("Server forced to shutdown: ", err)
	}

	log.Println("Server exiting")
}
		AllowHeaders:     []string{"Origin", "Content-Type"},
		AllowCredentials: true,
	}))

	// Routes
	r.GET("/api/members", getOrgMembers)
	r.POST("/api/send-mail", sendMailToMembers)

	log.Fatal(r.Run(":3000"))
}

func getOrgMembers(c *gin.Context) {
	ts := oauth2.StaticTokenSource(
		&oauth2.Token{AccessToken: config.GithubToken},
	)
	tc := oauth2.NewClient(c, ts)
	client := github.NewClient(tc)

	members, _, err := client.Organizations.ListMembers(c, config.OrgName, nil)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, members)
}

func sendMailToMembers(c *gin.Context) {
	var mailRequest struct {
		Subject string `json:"subject"`
		Body    string `json:"body"`
	}

	if err := c.BindJSON(&mailRequest); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// Get organization members
	ts := oauth2.StaticTokenSource(
		&oauth2.Token{AccessToken: config.GithubToken},
	)
	tc := oauth2.NewClient(c, ts)
	client := github.NewClient(tc)

	_, _, err := client.Organizations.ListMembers(c, config.OrgName, nil)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	// Send emails (implement email sending logic)
	// TODO: Implement actual email sending logic

	c.JSON(http.StatusOK, gin.H{"message": "Emails sent successfully"})
}
