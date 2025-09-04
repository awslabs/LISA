/**
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License").
 * You may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import { useState, useCallback, useEffect } from 'react';
import { useAuth } from 'react-oidc-context';

/**
 * Interface for encryption configuration
 */
interface EncryptionConfig {
  enabled: boolean;
  kmsKeyArn?: string;
}

/**
 * Interface for encrypted session data
 */
interface EncryptedSessionData {
  encrypted_key: string;
  encrypted_data: string;
  encryption_version: string;
}

/**
 * Custom hook for session encryption/decryption
 */
export const useSessionEncryption = () => {
  const { user } = useAuth();
  const [encryptionConfig, setEncryptionConfig] = useState<EncryptionConfig>({ enabled: false });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Check if encryption is enabled
  useEffect(() => {
    const checkEncryptionConfig = async () => {
      try {
        // This would typically come from a configuration API
        // For now, we'll check if the user has encryption enabled
        const config = await getEncryptionConfig();
        setEncryptionConfig(config);
      } catch (err) {
        console.error('Failed to get encryption config:', err);
        setError('Failed to load encryption configuration');
      }
    };

    checkEncryptionConfig();
  }, []);

  /**
   * Get encryption configuration from the backend
   */
  const getEncryptionConfig = async (): Promise<EncryptionConfig> => {
    try {
      const response = await fetch('/api/configuration/encryption', {
        headers: {
          'Authorization': `Bearer ${user?.access_token}`,
        },
      });
      
      if (!response.ok) {
        throw new Error('Failed to fetch encryption config');
      }
      
      return await response.json();
    } catch (error) {
      console.error('Error fetching encryption config:', error);
      // Return default config if API fails
      return { enabled: false };
    }
  };

  /**
   * Generate a data key from KMS
   */
  const generateDataKey = async (userId: string, sessionId: string): Promise<{ plaintext: string; encrypted: string }> => {
    try {
      const response = await fetch('/api/session/encryption/generate-key', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${user?.access_token}`,
        },
        body: JSON.stringify({
          userId,
          sessionId,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to generate data key');
      }

      return await response.json();
    } catch (error) {
      console.error('Error generating data key:', error);
      throw new Error('Failed to generate encryption key');
    }
  };

  /**
   * Encrypt session data
   */
  const encryptSessionData = useCallback(async (
    data: any,
    userId: string,
    sessionId: string
  ): Promise<string> => {
    if (!encryptionConfig.enabled) {
      return JSON.stringify(data);
    }

    setIsLoading(true);
    setError(null);

    try {
      // Generate data key
      const { plaintext, encrypted } = await generateDataKey(userId, sessionId);
      
      // Encrypt data using Web Crypto API
      const jsonData = JSON.stringify(data);
      const dataBuffer = new TextEncoder().encode(jsonData);
      
      // Import the key
      const key = await crypto.subtle.importKey(
        'raw',
        new TextEncoder().encode(plaintext.substring(0, 32)), // Use first 32 bytes
        { name: 'AES-GCM' },
        false,
        ['encrypt']
      );

      // Generate IV
      const iv = crypto.getRandomValues(new Uint8Array(12));
      
      // Encrypt the data
      const encryptedBuffer = await crypto.subtle.encrypt(
        { name: 'AES-GCM', iv },
        key,
        dataBuffer
      );

      // Combine IV and encrypted data
      const combined = new Uint8Array(iv.length + encryptedBuffer.byteLength);
      combined.set(iv);
      combined.set(new Uint8Array(encryptedBuffer), iv.length);

      // Create encrypted session data structure
      const encryptedSessionData: EncryptedSessionData = {
        encrypted_key: encrypted,
        encrypted_data: btoa(String.fromCharCode(...combined)),
        encryption_version: '1.0',
      };

      return btoa(JSON.stringify(encryptedSessionData));
    } catch (error) {
      console.error('Error encrypting session data:', error);
      setError('Failed to encrypt session data');
      throw new Error('Encryption failed');
    } finally {
      setIsLoading(false);
    }
  }, [encryptionConfig.enabled, user?.access_token]);

  /**
   * Decrypt session data
   */
  const decryptSessionData = useCallback(async (
    encryptedData: string,
    userId: string,
    sessionId: string
  ): Promise<any> => {
    if (!encryptionConfig.enabled) {
      return JSON.parse(encryptedData);
    }

    setIsLoading(true);
    setError(null);

    try {
      // Decode the encrypted data
      const encryptedSessionData: EncryptedSessionData = JSON.parse(atob(encryptedData));
      
      // Decrypt the data key
      const response = await fetch('/api/session/encryption/decrypt-key', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${user?.access_token}`,
        },
        body: JSON.stringify({
          encryptedKey: encryptedSessionData.encrypted_key,
          userId,
          sessionId,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to decrypt data key');
      }

      const { plaintext } = await response.json();

      // Decode the encrypted data
      const combined = new Uint8Array(
        atob(encryptedSessionData.encrypted_data)
          .split('')
          .map(char => char.charCodeAt(0))
      );

      // Extract IV and encrypted data
      const iv = combined.slice(0, 12);
      const encryptedBuffer = combined.slice(12);

      // Import the key
      const key = await crypto.subtle.importKey(
        'raw',
        new TextEncoder().encode(plaintext.substring(0, 32)), // Use first 32 bytes
        { name: 'AES-GCM' },
        false,
        ['decrypt']
      );

      // Decrypt the data
      const decryptedBuffer = await crypto.subtle.decrypt(
        { name: 'AES-GCM', iv },
        key,
        encryptedBuffer
      );

      // Convert back to string and parse JSON
      const decryptedText = new TextDecoder().decode(decryptedBuffer);
      return JSON.parse(decryptedText);
    } catch (error) {
      console.error('Error decrypting session data:', error);
      setError('Failed to decrypt session data');
      throw new Error('Decryption failed');
    } finally {
      setIsLoading(false);
    }
  }, [encryptionConfig.enabled, user?.access_token]);

  /**
   * Check if data appears to be encrypted
   */
  const isEncryptedData = useCallback((data: string): boolean => {
    try {
      const decoded = atob(data);
      const parsed = JSON.parse(decoded);
      return (
        typeof parsed === 'object' &&
        'encrypted_key' in parsed &&
        'encrypted_data' in parsed &&
        'encryption_version' in parsed
      );
    } catch {
      return false;
    }
  }, []);

  return {
    encryptionConfig,
    isLoading,
    error,
    encryptSessionData,
    decryptSessionData,
    isEncryptedData,
    isEncryptionEnabled: encryptionConfig.enabled,
  };
};

/**
 * Hook for managing session encryption state
 */
export const useSessionEncryptionState = () => {
  const [encryptionEnabled, setEncryptionEnabled] = useState<boolean>(false);
  const [migrationInProgress, setMigrationInProgress] = useState<boolean>(false);

  const toggleEncryption = useCallback(async (enabled: boolean) => {
    setMigrationInProgress(true);
    try {
      // This would typically call an API to update the encryption setting
      // and potentially migrate existing sessions
      const response = await fetch('/api/configuration/encryption', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ enabled }),
      });

      if (!response.ok) {
        throw new Error('Failed to update encryption setting');
      }

      setEncryptionEnabled(enabled);
    } catch (error) {
      console.error('Error toggling encryption:', error);
      throw error;
    } finally {
      setMigrationInProgress(false);
    }
  }, []);

  return {
    encryptionEnabled,
    migrationInProgress,
    toggleEncryption,
  };
};
