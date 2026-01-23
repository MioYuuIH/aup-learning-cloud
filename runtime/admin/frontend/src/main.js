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

const { createApp } = Vue

const app = createApp({
  data() {
    return {
      members: [],
      subject: '',
      body: '',
      loading: false,
      message: '',
      error: ''
    }
  },
  methods: {
    async fetchMembers() {
      try {
        this.loading = true
        const response = await axios.get('http://localhost:3000/api/members')
        this.members = response.data
        this.error = ''
      } catch (err) {
        this.error = 'Failed to fetch organization members'
        console.error(err)
      } finally {
        this.loading = false
      }
    },
    async sendMail() {
      if (!this.subject || !this.body) {
        this.error = 'Please fill in both subject and body'
        return
      }

      try {
        this.loading = true
        await axios.post('http://localhost:3000/api/send-mail', {
          subject: this.subject,
          body: this.body
        })
        this.message = 'Emails sent successfully!'
        this.error = ''
        this.subject = ''
        this.body = ''
      } catch (err) {
        this.error = 'Failed to send emails'
        console.error(err)
      } finally {
        this.loading = false
      }
    }
  },
  mounted() {
    this.fetchMembers()
  },
  template: `
    <div class="container mx-auto px-4 py-8">
      <h1 class="text-3xl font-bold mb-8">GitHub Organization Mailer</h1>
      
      <div v-if="error" class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
        {{ error }}
      </div>
      
      <div v-if="message" class="bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded mb-4">
        {{ message }}
      </div>

      <div class="mb-8">
        <h2 class="text-xl font-semibold mb-4">Organization Members</h2>
        <div v-if="loading">Loading...</div>
        <ul v-else class="list-disc pl-4">
          <li v-for="member in members" :key="member.id">{{ member.login }}</li>
        </ul>
      </div>

      <div class="mb-8">
        <h2 class="text-xl font-semibold mb-4">Send Email</h2>
        <form @submit.prevent="sendMail" class="space-y-4">
          <div>
            <label class="block text-sm font-medium mb-1">Subject</label>
            <input 
              v-model="subject"
              type="text"
              class="w-full px-3 py-2 border rounded"
              required
            >
          </div>
          
          <div>
            <label class="block text-sm font-medium mb-1">Body</label>
            <textarea
              v-model="body"
              class="w-full px-3 py-2 border rounded"
              rows="4"
              required
            ></textarea>
          </div>

          <button
            type="submit"
            :disabled="loading"
            class="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600 disabled:opacity-50"
          >
            {{ loading ? 'Sending...' : 'Send Email' }}
          </button>
        </form>
      </div>
    </div>
  `
})

app.mount('#app')
