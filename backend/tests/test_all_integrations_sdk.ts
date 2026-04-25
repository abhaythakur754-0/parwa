/**
 * PARWA Complete Integration Test - Using z-ai-web-dev-sdk
 * 
 * This script tests ALL PARWA integrations using SDK for testing.
 * It connects all working services and validates the complete pipeline.
 * 
 * Usage: npx ts-node backend/tests/test_all_integrations_sdk.ts
 */

import ZAI from 'z-ai-web-dev-sdk';
import https from 'https';
import http from 'http';
import { URL } from 'url';
import fs from 'fs';
import path from 'path';

// Test configuration
const TWILIO_ACCOUNT_SID = process.env.TWILIO_ACCOUNT_SID || '';
const TWILIO_AUTH_TOKEN = process.env.TWILIO_AUTH_TOKEN || '';
const TWILIO_PHONE_NUMBER = process.env.TWILIO_PHONE_NUMBER || '';
const TEST_PHONE_NUMBER = process.env.TEST_PHONE_NUMBER || '+919876543210';

const BREVO_API_KEY = process.env.BREVO_API_KEY || '';
const TEST_EMAIL = process.env.TEST_EMAIL || 'test@example.com';

interface TestResult {
  service: string;
  success: boolean;
  message: string;
  data?: Record<string, any>;
  error?: string;
  timestamp: string;
}

/**
 * Make HTTP request
 */
function makeRequest(
  url: string,
  options: {
    method?: string;
    headers?: Record<string, string>;
    body?: string;
    auth?: [string, string];
  } = {}
): Promise<{ status: number; data: any }> {
  return new Promise((resolve, reject) => {
    const parsedUrl = new URL(url);
    const isHttps = parsedUrl.protocol === 'https:';
    const lib = isHttps ? https : http;

    const reqOptions: any = {
      hostname: parsedUrl.hostname,
      port: parsedUrl.port || (isHttps ? 443 : 80),
      path: parsedUrl.pathname + parsedUrl.search,
      method: options.method || 'GET',
      headers: options.headers || {},
    };

    // Add basic auth if provided
    if (options.auth) {
      const authString = Buffer.from(`${options.auth[0]}:${options.auth[1]}`).toString('base64');
      reqOptions.headers['Authorization'] = `Basic ${authString}`;
    }

    const req = lib.request(reqOptions, (res) => {
      let data = '';
      res.on('data', (chunk) => (data += chunk));
      res.on('end', () => {
        try {
          const jsonData = JSON.parse(data);
          resolve({ status: res.statusCode || 0, data: jsonData });
        } catch {
          resolve({ status: res.statusCode || 0, data: data });
        }
      });
    });

    req.on('error', reject);
    
    if (options.body) {
      req.write(options.body);
    }
    
    req.end();
  });
}

/**
 * Test Twilio SMS
 */
async function testTwilioSMS(): Promise<TestResult> {
  const timestamp = new Date().toISOString();
  
  if (!TWILIO_ACCOUNT_SID || !TWILIO_AUTH_TOKEN || !TWILIO_PHONE_NUMBER) {
    return {
      service: 'twilio_sms',
      success: false,
      message: 'Missing Twilio credentials',
      error: 'Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER',
      timestamp,
    };
  }

  try {
    const url = `https://api.twilio.com/2010-04-01/Accounts/${TWILIO_ACCOUNT_SID}/Messages.json`;
    
    const body = new URLSearchParams({
      From: TWILIO_PHONE_NUMBER,
      To: TEST_PHONE_NUMBER,
      Body: `[PARWA Test] Integration test successful! Time: ${timestamp}`,
    }).toString();

    const response = await makeRequest(url, {
      method: 'POST',
      auth: [TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN],
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body,
    });

    if (response.status === 201) {
      console.log(`✅ Twilio SMS: SMS sent successfully - SID: ${response.data.sid}`);
      return {
        service: 'twilio_sms',
        success: true,
        message: 'SMS sent successfully',
        data: {
          sid: response.data.sid,
          status: response.data.status,
          to: response.data.to,
        },
        timestamp,
      };
    } else {
      console.log(`❌ Twilio SMS: HTTP ${response.status} - ${response.data.message || 'Unknown error'}`);
      return {
        service: 'twilio_sms',
        success: false,
        message: response.data.message || 'Failed to send SMS',
        error: `HTTP ${response.status}`,
        timestamp,
      };
    }
  } catch (error: any) {
    console.log(`❌ Twilio SMS Exception: ${error.message}`);
    return {
      service: 'twilio_sms',
      success: false,
      message: 'Exception during SMS test',
      error: error.message,
      timestamp,
    };
  }
}

/**
 * Test Twilio Voice
 */
async function testTwilioVoice(): Promise<TestResult> {
  const timestamp = new Date().toISOString();
  
  if (!TWILIO_ACCOUNT_SID || !TWILIO_AUTH_TOKEN || !TWILIO_PHONE_NUMBER) {
    return {
      service: 'twilio_voice',
      success: false,
      message: 'Missing Twilio credentials',
      error: 'Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER',
      timestamp,
    };
  }

  try {
    const url = `https://api.twilio.com/2010-04-01/Accounts/${TWILIO_ACCOUNT_SID}/Calls.json`;
    
    const twiml = `<Response><Say voice="alice">Hello! This is PARWA AI Assistant. Your integration test is successful. Thank you!</Say></Response>`;
    
    const body = new URLSearchParams({
      From: TWILIO_PHONE_NUMBER,
      To: TEST_PHONE_NUMBER,
      Twiml: twiml,
    }).toString();

    const response = await makeRequest(url, {
      method: 'POST',
      auth: [TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN],
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body,
    });

    if (response.status === 201) {
      console.log(`✅ Twilio Voice: Call initiated - SID: ${response.data.sid}`);
      return {
        service: 'twilio_voice',
        success: true,
        message: 'Voice call initiated (trial account has limitations)',
        data: {
          sid: response.data.sid,
          status: response.data.status,
          to: response.data.to,
        },
        timestamp,
      };
    } else {
      console.log(`❌ Twilio Voice: HTTP ${response.status} - ${response.data.message || 'Unknown error'}`);
      return {
        service: 'twilio_voice',
        success: false,
        message: response.data.message || 'Failed to initiate call',
        error: `HTTP ${response.status}`,
        timestamp,
      };
    }
  } catch (error: any) {
    console.log(`❌ Twilio Voice Exception: ${error.message}`);
    return {
      service: 'twilio_voice',
      success: false,
      message: 'Exception during voice test',
      error: error.message,
      timestamp,
    };
  }
}

/**
 * Test Brevo Email
 */
async function testBrevoEmail(): Promise<TestResult> {
  const timestamp = new Date().toISOString();
  
  if (!BREVO_API_KEY) {
    return {
      service: 'brevo_email',
      success: false,
      message: 'Missing Brevo API key',
      error: 'Set BREVO_API_KEY environment variable',
      timestamp,
    };
  }

  try {
    const url = 'https://api.brevo.com/v3/smtp/email';
    
    const payload = {
      sender: {
        name: 'PARWA AI',
        email: 'noreply@parwa.ai',
      },
      to: [{ email: TEST_EMAIL }],
      subject: `PARWA Integration Test - ${timestamp}`,
      htmlContent: `
        <html>
        <body style="font-family: Arial, sans-serif;">
          <h2 style="color: #10b981;">PARWA Integration Test Successful!</h2>
          <p>Your PARWA email integration is working correctly.</p>
          <p>Test completed at: ${timestamp}</p>
        </body>
        </html>
      `,
      textContent: `PARWA Integration Test Successful! Time: ${timestamp}`,
    };

    const response = await makeRequest(url, {
      method: 'POST',
      headers: {
        'api-key': BREVO_API_KEY,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });

    if (response.status === 200 || response.status === 201) {
      console.log(`✅ Brevo Email: Email sent - ID: ${response.data.messageId}`);
      return {
        service: 'brevo_email',
        success: true,
        message: 'Email sent successfully',
        data: {
          messageId: response.data.messageId,
          to: TEST_EMAIL,
        },
        timestamp,
      };
    } else {
      console.log(`❌ Brevo Email: HTTP ${response.status} - ${response.data.message || 'Unknown error'}`);
      return {
        service: 'brevo_email',
        success: false,
        message: response.data.message || 'Failed to send email',
        error: `HTTP ${response.status}`,
        timestamp,
      };
    }
  } catch (error: any) {
    console.log(`❌ Brevo Email Exception: ${error.message}`);
    return {
      service: 'brevo_email',
      success: false,
      message: 'Exception during email test',
      error: error.message,
      timestamp,
    };
  }
}

/**
 * Test AI Chat via SDK
 */
async function testAIChatSDK(): Promise<TestResult> {
  const timestamp = new Date().toISOString();
  
  try {
    const zai = await ZAI.create();
    
    const completion = await zai.chat.completions.create({
      messages: [
        {
          role: 'system',
          content: 'You are PARWA AI Assistant. Respond concisely and professionally.',
        },
        {
          role: 'user',
          content: "This is an integration test. Please confirm you're working by saying 'PARWA AI is online and ready!'",
        },
      ],
    });

    if (completion && completion.choices && completion.choices.length > 0) {
      const content = completion.choices[0].message.content;
      console.log(`✅ AI Chat SDK: Working - Response: ${content.substring(0, 100)}...`);
      return {
        service: 'ai_chat_sdk',
        success: true,
        message: 'AI chat working successfully',
        data: {
          response: content,
          model: completion.model || 'unknown',
        },
        timestamp,
      };
    } else {
      console.log(`❌ AI Chat SDK: Empty response`);
      return {
        service: 'ai_chat_sdk',
        success: false,
        message: 'Empty response from AI',
        error: 'No choices in response',
        timestamp,
      };
    }
  } catch (error: any) {
    console.log(`❌ AI Chat SDK Exception: ${error.message}`);
    return {
      service: 'ai_chat_sdk',
      success: false,
      message: 'Exception during AI chat test',
      error: error.message,
      timestamp,
    };
  }
}

/**
 * Test AI Image Generation via SDK
 */
async function testAIImageSDK(): Promise<TestResult> {
  const timestamp = new Date().toISOString();
  
  try {
    const zai = await ZAI.create();
    
    const response = await zai.images.generations.create({
      prompt: 'A professional logo for PARWA AI customer support system, modern minimalist design, green and blue colors',
      size: '1024x1024',
    });

    if (response && response.data && response.data.length > 0) {
      const imageSize = response.data[0].base64 ? response.data[0].base64.length : 0;
      console.log(`✅ AI Image SDK: Working - Generated image size: ${imageSize} bytes`);
      return {
        service: 'ai_image_sdk',
        success: true,
        message: 'AI image generation working',
        data: {
          hasImage: true,
          imageSize,
        },
        timestamp,
      };
    } else {
      console.log(`❌ AI Image SDK: No image generated`);
      return {
        service: 'ai_image_sdk',
        success: false,
        message: 'No image generated',
        error: 'Empty response',
        timestamp,
      };
    }
  } catch (error: any) {
    console.log(`❌ AI Image SDK Exception: ${error.message}`);
    return {
      service: 'ai_image_sdk',
      success: false,
      message: 'Exception during image generation test',
      error: error.message,
      timestamp,
    };
  }
}

/**
 * Test Web Search via SDK
 */
async function testWebSearchSDK(): Promise<TestResult> {
  const timestamp = new Date().toISOString();
  
  try {
    const zai = await ZAI.create();
    
    const searchResult = await zai.functions.invoke('web_search', {
      query: 'PARWA AI customer support system',
      num: 5,
    });

    if (searchResult) {
      const resultsCount = Array.isArray(searchResult) ? searchResult.length : 1;
      console.log(`✅ Web Search SDK: Working - Found ${resultsCount} results`);
      return {
        service: 'web_search_sdk',
        success: true,
        message: 'Web search working',
        data: {
          resultsCount,
          hasResults: true,
        },
        timestamp,
      };
    } else {
      console.log(`❌ Web Search SDK: No results`);
      return {
        service: 'web_search_sdk',
        success: false,
        message: 'No search results',
        error: 'Empty response',
        timestamp,
      };
    }
  } catch (error: any) {
    console.log(`❌ Web Search SDK Exception: ${error.message}`);
    return {
      service: 'web_search_sdk',
      success: false,
      message: 'Exception during web search test',
      error: error.message,
      timestamp,
    };
  }
}

/**
 * Run all tests
 */
async function runAllTests(): Promise<void> {
  console.log('='.repeat(70));
  console.log('  PARWA COMPLETE INTEGRATION TEST - Using z-ai-web-dev-sdk');
  console.log('='.repeat(70));
  console.log(`  Test Time: ${new Date().toISOString()}`);
  console.log('='.repeat(70));
  console.log();

  const results: TestResult[] = [];

  // Run all tests
  console.log('▶ Running: Twilio SMS...');
  results.push(await testTwilioSMS());
  
  console.log('\n▶ Running: Twilio Voice...');
  results.push(await testTwilioVoice());
  
  console.log('\n▶ Running: Brevo Email...');
  results.push(await testBrevoEmail());
  
  console.log('\n▶ Running: AI Chat SDK...');
  results.push(await testAIChatSDK());
  
  console.log('\n▶ Running: AI Image SDK...');
  results.push(await testAIImageSDK());
  
  console.log('\n▶ Running: Web Search SDK...');
  results.push(await testWebSearchSDK());

  // Summary
  console.log('\n' + '='.repeat(70));
  console.log('  INTEGRATION TEST SUMMARY');
  console.log('='.repeat(70));

  const passed = results.filter((r) => r.success).length;
  const total = results.length;

  for (const r of results) {
    const status = r.success ? '✅ PASS' : '❌ FAIL';
    console.log(`${status} - ${r.service}: ${r.message}`);
    if (r.error) {
      console.log(`   Error: ${r.error}`);
    }
  }

  console.log('='.repeat(70));
  console.log(`Total: ${passed}/${total} tests passed`);
  console.log('='.repeat(70));

  // Save report
  const report = {
    timestamp: new Date().toISOString(),
    summary: {
      total,
      passed,
      failed: total - passed,
      passRate: total > 0 ? `${((passed / total) * 100).toFixed(1)}%` : '0%',
    },
    results,
  };

  const reportPath = '/home/z/my-project/download/parwa_integration_report.json';
  fs.mkdirSync(path.dirname(reportPath), { recursive: true });
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));

  console.log(`\n📄 Report saved to: ${reportPath}`);
}

// Run tests
runAllTests().catch(console.error);
