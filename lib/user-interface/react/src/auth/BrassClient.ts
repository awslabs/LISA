/**
 * BRASS Authorization Request Interface
 */
interface BrassRequest {
  actor: {
    actorType: 'principal' | 'role' | 'service';
    actorId: string;
  };
  operation: 'Unlock' | 'Access' | 'Read' | 'Write';
  resource: {
    namespace: 'Bindle' | string;
    resourceType: 'Lock' | string;
    resourceName: string;
  };
}

/**
 * BRASS Authorization Response Interface
 */
interface BrassResponse {
  authorized: boolean;
  user: string;
  bindleLock: string;
  request: BrassRequest;
  brassResponse: {
    authorized: boolean;
    user: string;
    operation: string;
    resource: {
      namespace: string;
      resourceType: string;
      resourceName: string;
    };
  };
  [key: string]: any;
}

/**
 * BRASS Client Error Types
 */
export class BrassClientError extends Error {
  constructor(message: string, public statusCode?: number, public response?: any) {
    super(message);
    this.name = 'BrassClientError';
  }
}

/**
 * Browser-compatible BrassClient for frontend BRASS authorization requests.
 * 
 * This client handles communication with the backend BRASS authorization API
 * and provides type-safe methods for checking bindle lock permissions.
 * 
 * @example
 * ```typescript
 * const client = new BrassClient();
 * const result = await client.isAuthorizedToUnlockBindle('username', 'amzn1.bindle.resource.xxx');
 * if (result.authorized) {
 *   // User has access
 * }
 * ```
 */
export default class BrassClient {
  private readonly baseUrl: string;
  private readonly timeout: number;

  constructor(baseUrl: string = '', timeout: number = 30000) {
    this.baseUrl = baseUrl;
    this.timeout = timeout;
  }

  /**
   * Checks if a user is authorized to unlock a bindle lock
   * 
   * @param user - The Amazon username of the user (required, non-empty)
   * @param bindleLock - The bindle lock identifier (required, must be valid GUID format)
   * @returns Promise that resolves to the authorization response
   * @throws {BrassClientError} When the request fails or validation errors occur
   * @throws {Error} When input validation fails
   */
  async isAuthorizedToUnlockBindle(user: string, bindleLock: string): Promise<BrassResponse> {
    // Input validation
    if (!user || typeof user !== 'string' || !user.trim()) {
      throw new Error('User parameter is required and must be a non-empty string');
    }
    
    if (!bindleLock || typeof bindleLock !== 'string' || !bindleLock.trim()) {
      throw new Error('BindleLock parameter is required and must be a non-empty string');
    }

    // Validate bindle GUID format (basic validation)
    if (!bindleLock.startsWith('amzn1.bindle.resource.')) {
      throw new Error('BindleLock must be a valid Amazon bindle resource GUID');
    }

    const brassRequest: BrassRequest = {
      actor: {
        actorType: 'principal',
        actorId: user.trim()
      },
      operation: 'Unlock',
      resource: {
        namespace: 'Bindle',
        resourceType: 'Lock',
        resourceName: bindleLock.trim()
      }
    };

    try {
      console.info(`[BrassClient] Checking authorization for user: ${user} on bindle: ${bindleLock}`);
      
      // Create AbortController for timeout handling
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), this.timeout);

      const response = await fetch(`${this.baseUrl}/brass/authorize`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        body: JSON.stringify(brassRequest),
        signal: controller.signal
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        const errorText = await response.text().catch(() => 'Unknown error');
        throw new BrassClientError(
          `BRASS authorization request failed: ${response.status} ${response.statusText}`,
          response.status,
          errorText
        );
      }

      const apiGatewayResponse = await response.json();
      
      // Handle API Gateway response format - the actual BRASS response is in the 'body' field
      let result: BrassResponse;
      if (apiGatewayResponse.body && typeof apiGatewayResponse.body === 'string') {
        // API Gateway response format - body is JSON stringified
        try {
          result = JSON.parse(apiGatewayResponse.body);
        } catch (parseError) {
          throw new BrassClientError('Invalid response format: failed to parse response body JSON');
        }
      } else if (apiGatewayResponse.authorized !== undefined) {
        // Direct response format (backward compatibility)
        result = apiGatewayResponse;
      } else {
        throw new BrassClientError('Invalid response format: missing expected response structure');
      }
      
      // Validate response structure
      if (typeof result.authorized !== 'boolean') {
        throw new BrassClientError('Invalid response format: missing or invalid authorized field');
      }

      console.info(`[BrassClient] Authorization result for ${user}: ${result.authorized}`);
      return result;

    } catch (error) {
      if (error.name === 'AbortError') {
        throw new BrassClientError(`BRASS authorization request timed out after ${this.timeout}ms`);
      }
      
      if (error instanceof BrassClientError) {
        throw error;
      }
      
      console.error('[BrassClient] Error checking BRASS authorization:', error);
      throw new BrassClientError(
        `Failed to check BRASS authorization: ${error.message}`,
        undefined,
        error
      );
    }
  }

  /**
   * Batch check multiple bindle lock authorizations (if supported by backend)
   * 
   * @param user - The Amazon username of the user
   * @param bindleLocks - Array of bindle lock identifiers
   * @returns Promise that resolves to array of authorization responses
   */
  async batchCheckBindleLocks(user: string, bindleLocks: string[]): Promise<BrassResponse[]> {
    // For now, implement as sequential calls
    // TODO: Implement actual batch API when available
    const results: BrassResponse[] = [];
    
    for (const bindleLock of bindleLocks) {
      try {
        const result = await this.isAuthorizedToUnlockBindle(user, bindleLock);
        results.push(result);
      } catch (error) {
        // For batch operations, continue with other checks even if one fails
        console.warn(`[BrassClient] Failed to check bindle ${bindleLock} for user ${user}:`, error);
        results.push({
          authorized: false,
          user,
          bindleLock,
          request: {
            actor: { actorType: 'principal', actorId: user },
            operation: 'Unlock',
            resource: { namespace: 'Bindle', resourceType: 'Lock', resourceName: bindleLock }
          },
          brassResponse: {
            authorized: false,
            user,
            operation: 'Unlock',
            resource: { namespace: 'Bindle', resourceType: 'Lock', resourceName: bindleLock }
          },
          error: error.message
        });
      }
    }
    
    return results;
  }
}
