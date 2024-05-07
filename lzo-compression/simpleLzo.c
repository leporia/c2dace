#include <stdio.h>
#include <memory.h>
#include <immintrin.h>
#include <sys/stat.h>

int main(int argc, char** argv)
{
	int aa,numIterations;
	FILE* infile;
	unsigned long numRead;
	int outfile;
	
	unsigned int compressionBlockSizeBytes;
	unsigned int bufferedBytes = 0;

	unsigned int blockSize;
	unsigned char* inputBuffer;
	char* dictMem;
	unsigned char* outputBuffer;

	unsigned long blockStartCount,blockEndCount,blockFullCount, numberOfInputBlocks;

	unsigned long fileSize, totalOutlen;
	compressionBlockSizeBytes = 262144;

	/***********************************************/
	/* Parse command line parameters if they exist */
	/***********************************************/
	numIterations = 50;

	/* Determine Read buffersize, needs to be a multiple of block size */
	unsigned int read_buffer_size = ((512*1024*1024)/compressionBlockSizeBytes) * (compressionBlockSizeBytes);


	/* Force Max Filesize to 512MBytes */
	if(fileSize > read_buffer_size)
		fileSize = read_buffer_size;


	/* Allocate memory buffers */
	inputBuffer = malloc(536970912);
	outputBuffer = malloc(590558003);
	dictMem = malloc(1048576);	/* 1MB */

	/* Open the file for reading */
    infile = fopen("input.txt","rb");

	/* Fill the Input Buffer For Compresssion */
	numRead = fread(inputBuffer,1,read_buffer_size,infile);
	fclose(infile);

	printf("Beginning Compression of %s, Size = %d bytes, Iter=%d.\n","input.txt",numRead,numIterations);


	numberOfInputBlocks = 0;

	for(aa=0;aa<numIterations;aa++)
	{
		printf("Running iteration %d\n", aa);
		blockFullCount = 0;
		unsigned char* pInputBuffer;
		pInputBuffer = inputBuffer;
		fileSize = numRead;
		bufferedBytes = numRead;

		totalOutlen = 0;
		
		/* Set the input block size */
		blockSize = compressionBlockSizeBytes;
		if(fileSize < blockSize)
			blockSize = fileSize;

		/* Get Start Count and Begin Iterating until FileSize <= 0 */
		while(fileSize > 0)
		{
			printf("Running block %d\n", numberOfInputBlocks);
			unsigned char* ip = pInputBuffer;
			unsigned char* op = outputBuffer;
			unsigned int l = blockSize;
			unsigned int t = 0;

			while (l > 31) {
				printf("Running inside %u\n", l);
				unsigned long ll = l;
				unsigned char* ll_end = ip;
				/* Note throughput increase if you can fit everything in L1 cache? */
				if (ll > 49152) {
					ll = 49152;	
				}
				ll_end = ip + ll;

				memset(dictMem, 0, ((unsigned int)1 << 13 /*DBITS*/) * sizeof(unsigned short));

				unsigned char* ip_block;
				unsigned char* in_end = pInputBuffer + ll;
				unsigned char* ip_block_end = pInputBuffer;
				ip_block_end += ll;
				ip_block_end -= 20;
				unsigned char* ii;
				unsigned short* dict = dictMem;

				op = outputBuffer;
				ip_block = pInputBuffer;
				ii = pInputBuffer;

				ip_block += 5;
				unsigned char cond_ipblock;
				cond_ipblock = ip_block < ip_block_end;
				while (cond_ipblock) {
					printf("ip cond\n");
					unsigned char* m_pos;
					m_pos = pInputBuffer;

					unsigned int m_off;
					unsigned int m_len;
					unsigned int dv;
					unsigned int dindex;

					dv = ((unsigned int*) ip_block)[0];
					dindex = ((dv * 0x1824429D) >> 19) & 0x1FFF;	/* Determine dictionary index that maps to the new data value.		*/
					m_pos = pInputBuffer + dict[dindex];	/* Obtain absolute address of the current dictionary entry match.	*/
					dict[dindex] = ip_block-pInputBuffer;		/* Update dictionary entry to point to the latest value, store relative offset. */

					while (dv != ((unsigned int*) m_pos)[0]) {
						unsigned int diff;
						diff = ip_block - ii;
						ip_block += 1 + (diff >> 5);
						if (ip_block >= ip_block_end) {
							break;
						}
						dv = ((unsigned int*) ip_block)[0];
						dindex = ((dv * 0x1824429D) >> 19) & 0x1FFF;	/* Determine dictionary index that maps to the new data value.		*/
						m_pos = pInputBuffer + dict[dindex];	/* Obtain absolute address of the current dictionary entry match.	*/
						dict[dindex] = ip_block-pInputBuffer;		/* Update dictionary entry to point to the latest value, store relative offset. */
					}

					/* a match */
					unsigned int t_inner;
					t_inner = ip_block-ii;
					if (t_inner != 0)
					{
						if (t_inner <= 3)
						{
							op -= 2;
							op[0] |= (unsigned char)(t_inner);
							op += 2;
							((unsigned int*) op)[0] = ((unsigned int*) ii)[0];
							op += t_inner;
						}
						else if (t_inner <= 16)
						{
							op[0] = (unsigned char)(t_inner - 3);
							op++;
							((unsigned int*) op)[0] = ((unsigned int*) ii)[0];
							((unsigned int*) (op))[1] = ((unsigned int*) (ii))[1];
							((unsigned int*) (op))[2] = ((unsigned int*) (ii))[2];
							((unsigned int*) (op))[3] = ((unsigned int*) (ii))[3];
							op += t_inner;
						}
						else
						{
							if (t_inner <= 18) {
								op[0] = (unsigned char)(t_inner - 3);
								op++;
							} else
							{
								op[0] = 0;
								op++;
								unsigned int tt = t_inner - 18;
								for (tt = t_inner-18; tt > 255; tt-=255) {
									((unsigned char *) op)[0] = 0;
									op++;
								}
								op[0] = (unsigned char)(tt);
								op++;
							}

							for (int i=0; i < t_inner; i++) {
								op[0] = ii[0];
								op++;
								ii++;
							}
						}
					}
					


					m_len = 4;
					unsigned int bytematch;
					unsigned int v;
					unsigned int op1, op2;
					op1 = ((unsigned int*) ip_block)[m_len/4];
					op2 = ((unsigned int*) m_pos)[m_len/4];
					v = op1 ^ op2;
					if (v == 0) {
						m_len += 4;
						op1 = ((unsigned int*) ip_block)[m_len/4];
						op2 = ((unsigned int*) m_pos)[m_len/4];
						v = op1 ^ op2;
						unsigned char* ip_curr = ip_block;
						ip_curr = ip_block + m_len;
						unsigned char cond_w;
						cond_w = ip_curr < ip_block_end;
						while (v == 0 && cond_w) {
							m_len += 4;
							op1 = ((unsigned int*) ip_block)[m_len/4];
							op2 = ((unsigned int*) m_pos)[m_len/4];
							v = op1 ^ op2;
							ip_curr = ip_block + m_len;
							cond_w = ip_curr < ip_block_end;
						}
					}

					unsigned char* ip_curr_2;
					ip_curr_2 = ip_block + m_len;
					if (ip_curr_2 < ip_block_end) {
						bytematch = _bit_scan_forward(v);
						m_len += (bytematch/8);
					}


					m_off = ip_block-m_pos;
					ip_block += m_len;
					printf("move block by %u\n", m_len);
					ii = ip_block;
					if (m_len <= 8 && m_off <= 0x800)
					{
						m_off -= 1;
						op[0] = (unsigned char)(((m_len - 1) << 5) | ((m_off & 7) << 2));
						op++;
						op[0] = (unsigned char)(m_off >> 3);
						op++;
					}
					else if (m_off <= 0x4000)
					{
						m_off -= 1;
						if (m_len <= 33) {
							op[0] = (unsigned char)(0x20 | (m_len - 2));
							op++;
						} else
						{
							m_len -= 33;
							op[0] = 0x20 | 0;
							op++;
							while (m_len > 255)
							{
								m_len -= 255;
								((unsigned char *) op)[0] = 0;
								op++;
							}
							op[0] = (unsigned char)(m_len);
							op++;
						}
						op[0] = (unsigned char)(m_off << 2);
						op++;
						op[0] = (unsigned char)(m_off >> 6);
						op++;
					}
					else
					{
						m_off -= 0x4000;
						if (m_len <= 0x9) {
							op[0] = (unsigned char)(0x10 | ((m_off >> 11) & 8) | (m_len - 2));
							op++;
						} else
						{
							m_len -= 0x9;
							op[0] = (unsigned char)(0x10 | ((m_off >> 11) & 8));
							op++;
							while (m_len > 255)
							{
								m_len -= 255;
								((unsigned char *) op)[0] = 0;
								op++;
							}
							op[0] = (unsigned char)(m_len);
							op++;
						}
						op[0] = (unsigned char)(m_off << 2);
						op++;
						op[0] = (unsigned char)(m_off >> 6);
						op++;
					}
					cond_ipblock = ip_block < ip_block_end;
				}

				t = in_end - ip_block;

				printf("end subtraction %d\n", t);
				ip += ll;
				l  -= ll;
			}

			printf("post while %d\n", t);

			t += l;

			if (t > 0)
			{
				unsigned char* ii = pInputBuffer + blockSize - t;
				unsigned char eq;
				eq = op == outputBuffer;
				if (eq && t <= 238) {
					op[0] = (unsigned char)(17 + t);
					op++;
				} else if (t <= 3) {
					op[0] |= (unsigned char)(t);
				} else if (t <= 18) {
					op[0] = (unsigned char)(t - 3);
					op++;
				} else
				{
					op[0] = 0;
					op++;
					unsigned int tt;
					for (tt = t-18; tt > 255; tt-=255) {
						((unsigned char *) op)[0] = 0;
						op++;
					}
					op[0] = (unsigned char)(tt);
					op++;
				}

				for (int i=0; i<t; i++) {
					op[0] = ii[0];
					op++;
					ii++;
				}
			}

			op[0] = 0x10 | 1;
			op++;
			op[0] = 0;
			op++;
			op[0] = 0;
			op++;

			long outlen_temp;
			outlen_temp = op - outputBuffer;
			totalOutlen += outlen_temp; //pd(op, out);

			if(blockEndCount > blockStartCount)
			{
				blockFullCount += blockEndCount - blockStartCount;
			}
			else
			{
				//Account for roll-over situation if it occurs
				blockFullCount += (0xFFFFFFFFFFFFFFFF - blockEndCount) + blockStartCount + 1;
			}
			
			numberOfInputBlocks++;
			pInputBuffer+=blockSize;					//Advance Input Pointer

			fileSize-= blockSize;				//Update Remaining Filesize
			bufferedBytes -= blockSize;					//Update Remaining Bytes in the current memory read buffer
			if(fileSize < blockSize)			//Update Block Size when only a remainder size exists
				blockSize = fileSize;
		}
	}

	FILE* out = fopen("out_file.txt","w");
	fwrite(outputBuffer,1,totalOutlen,out);
	fclose(out);

	// force to keep this
	printf("out %u\n", outputBuffer[0]);

	free(inputBuffer);
	free(dictMem);
	free(outputBuffer);

	return 0;
}