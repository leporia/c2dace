#include <stdio.h>
#include <memory.h>
#include <immintrin.h>
#include <sys/stat.h>

#define DEFAULT_BLOCK_SIZE		262144	/* 256kB */
#define OUTPUT_FILE_NAME        "out_file.txt"

/* Size of Memory Buffer */
#define BUFFER_SIZE	(512*1024*1024)		/* NOTE: MUST BE A MULTIPLE OF BLOCK SIZE IN ORDER FOR PROGRAM TO WORK PROPERLY!!! */
										/* Can get around this with more coding, but for benchmarking purposes, not necessary or useful */

unsigned int G_RD_BUFFER_SIZE;


#define LZO_HASH_VALUE		0x1824429D
#define lzo_uint	unsigned int
#define lzo_uint32	unsigned int
#define LZO_BYTE	(unsigned char)
#define UA_GET32(a)		*((unsigned int*)(a))
#define UA_COPY32(a,b)	*((unsigned int*)(a)) = *((unsigned int*)(b))
#define CHAR_BIT	8

#define M2_MAX_LEN		8
#define M2_MAX_OFFSET	0x800
#define M3_MAX_OFFSET	0x4000

#define M3_MARKER	0x20
#define M4_MARKER	0x10
#define M3_MAX_LEN	33
#define M4_MAX_LEN	0x9

#define LZO_MIN(a,b)        ((a) <= (b) ? (a) : (b))


static unsigned int
do_compress ( const unsigned char* in , unsigned int  in_len,
                    unsigned char* out, unsigned int* out_len,
                    unsigned int  ti,  void* wrkmem);




int lzo1x_1_15_compress( const unsigned char* in, unsigned int  in_len,
                         unsigned char* out, unsigned int* out_len,
                         void* wrkmem )
{
	const unsigned char* ip = in;
	unsigned char* op = out;
    unsigned int l = in_len;
    unsigned int t = 0;

    while (l > 20)
    {
        size_t ll = l;
        size_t ll_end;
		/* Note throughput increase if you can fit everything in L1 cache? */
        ll = LZO_MIN(ll, 49152 /*25600 30720*/ );
        ll_end = (((size_t)ip) + ll);
        if ((ll_end + ((t + ll) >> 5)) <= ll_end || (const unsigned char*)(ll_end + ((t + ll) >> 5)) <= ip + ll)
            break;

        memset(wrkmem, 0, ((unsigned int)1 << 13 /*DBITS*/) * sizeof(unsigned short));

        t = do_compress(ip,ll,op,out_len,t,wrkmem);
        ip += ll;
        op += *out_len;
        l  -= ll;
    }
    t += l;

    if (t > 0)
    {
        const unsigned char* ii = in + in_len - t;

        if (op == out && t <= 238)
            *op++ = (unsigned char)(17 + t);
        else if (t <= 3)
            op[-2] |= (unsigned char)(t);
        else if (t <= 18)
            *op++ = (unsigned char)(t - 3);
        else
        {
            unsigned int tt = t - 18;
            *op++ = 0;
            while (tt > 255)
            {
                tt -= 255;

                /* prevent the compiler from transforming this loop
                 * into a memset() call */
                * (volatile unsigned char *) op++ = 0;
            }
            *op++ = (unsigned char)(tt);
        }
        do *op++ = *ii++; while (--t > 0);
    }

    *op++ = M4_MARKER | 1;
    *op++ = 0;
    *op++ = 0;

    *out_len = op - out; //pd(op, out);

	return 0; //LZO_E_OK;
}















/***********************************************************************
// compress a block of data.
************************************************************************/

static unsigned int
do_compress ( const unsigned char* in , unsigned int  in_len,
                    unsigned char* out, unsigned int* out_len,
                    unsigned int  ti,  void* wrkmem)
{
    register const unsigned char* ip;
    unsigned char* op;
    const unsigned char* const in_end = in + in_len;
    const unsigned char* const ip_end = in + in_len - 20;
    const unsigned char* ii;
    unsigned short* const dict = (unsigned short*) wrkmem;

    op = out;
    ip = in;
    ii = ip;

    ip += ti < 4 ? 4 - ti : 0;

    for (;;)
    {
        const unsigned char* m_pos;

        lzo_uint m_off;
        lzo_uint m_len;
        {
			lzo_uint32 dv;
			lzo_uint dindex;
literal:
	        ip += 1 + ((ip - ii) >> 5);
next:
			if (ip >= ip_end)
	            break;
	        dv = UA_GET32(ip);
	        //dindex = DINDEX(dv,ip);
	        //GINDEX(m_off,m_pos,in+dict,dindex,in);
	        //UPDATE_I(dict,0,dindex,ip,in);
			dindex = ((dv * LZO_HASH_VALUE) >> 19) & 0x1FFF;	/* Determine dictionary index that maps to the new data value.		*/
			m_pos = in + dict[dindex];	/* Obtain absolute address of the current dictionary entry match.	*/
			dict[dindex] = ip-in;		/* Update dictionary entry to point to the latest value, store relative offset. */

	        if (dv != UA_GET32(m_pos))
	            goto literal;
        }


		/* a match */
        ii -= ti; ti = 0;
        {
	        register lzo_uint t = (ip-ii);
	        if (t != 0)
	        {
		        if (t <= 3)
	            {
		            op[-2] |= LZO_BYTE(t);
	               UA_COPY32(op, ii);
	                op += t;
				}
				else if (t <= 16)
				{
					*op++ = LZO_BYTE(t - 3);
					UA_COPY32(op, ii);
					UA_COPY32(op+4, ii+4);
					UA_COPY32(op+8, ii+8);
					UA_COPY32(op+12, ii+12);
					op += t;
				}
				else
				{
					if (t <= 18)
						*op++ = LZO_BYTE(t - 3);
					else
					{
						register lzo_uint tt = t - 18;
						*op++ = 0;
						while (tt > 255)
						{
							tt -= 255;
							* (volatile unsigned char *) op++ = 0;
						}
						*op++ = LZO_BYTE(tt);
					}
					do {
						UA_COPY32(op, ii);
						UA_COPY32(op+4, ii+4);
						UA_COPY32(op+8, ii+8);
						UA_COPY32(op+12, ii+12);
						op += 16; ii += 16; t -= 16;
					} while (t >= 16); if (t > 0)

					{ do *op++ = *ii++; while (--t > 0); }
				}
			}
        }
        


		m_len = 4;
        {
			unsigned int bytematch;
	        lzo_uint32 v;
		    v = UA_GET32(ip + m_len) ^ UA_GET32(m_pos + m_len);
	        if (v == 0) 
			{
				do {
					m_len += 4;
					v = UA_GET32(ip + m_len) ^ UA_GET32(m_pos + m_len);
					if (ip + m_len >= ip_end)
						goto m_len_done;
				} while (v == 0);
	        }

	        //m_len += lzo_bitops_ctz32(v) / CHAR_BIT;
			bytematch = _bit_scan_forward(v);	/* ASM BSF */
			m_len += (bytematch/8);
		}


m_len_done:
        m_off = (ip-m_pos);		
        ip += m_len;
        ii = ip;
        if (m_len <= M2_MAX_LEN && m_off <= M2_MAX_OFFSET)
        {
            m_off -= 1;
            *op++ = LZO_BYTE(((m_len - 1) << 5) | ((m_off & 7) << 2));
            *op++ = LZO_BYTE(m_off >> 3);
        }
        else if (m_off <= M3_MAX_OFFSET)
        {
            m_off -= 1;
            if (m_len <= M3_MAX_LEN)
                *op++ = LZO_BYTE(M3_MARKER | (m_len - 2));
            else
            {
                m_len -= M3_MAX_LEN;
                *op++ = M3_MARKER | 0;
                while (m_len > 255)
                {
                    m_len -= 255;
                    * (volatile unsigned char *) op++ = 0;
                }
                *op++ = LZO_BYTE(m_len);
            }
            *op++ = LZO_BYTE(m_off << 2);
            *op++ = LZO_BYTE(m_off >> 6);
        }
        else
        {
            m_off -= 0x4000;
            if (m_len <= M4_MAX_LEN)
                *op++ = LZO_BYTE(M4_MARKER | ((m_off >> 11) & 8) | (m_len - 2));
            else
            {
                m_len -= M4_MAX_LEN;
                *op++ = LZO_BYTE(M4_MARKER | ((m_off >> 11) & 8));
                while (m_len > 255)
                {
                    m_len -= 255;
                    * (volatile unsigned char *) op++ = 0;
                }
                *op++ = LZO_BYTE(m_len);
            }
            *op++ = LZO_BYTE(m_off << 2);
            *op++ = LZO_BYTE(m_off >> 6);
        }
        goto next;
    }

    *out_len = op - out;
    return in_end - (ii-ti);
}

int main(int argc, char** argv)
{
	int aa,numIterations;
	FILE* infile = NULL;
	size_t numRead;
	FILE* outfile = NULL;
	
	unsigned int compressionBlockSizeBytes;
	unsigned int bufferedBytes = 0;

	unsigned int outLength;
	unsigned int blockSize;
	static char inputfname[300];
	unsigned char* inputBuffer = NULL;
	unsigned char* pInputBuffer = NULL;
	char* dictMem = NULL;
	unsigned char* outputBuffer = NULL;

	size_t blockStartCount,blockEndCount,blockFullCount, numberOfInputBlocks;

	size_t fileSize, totalOutlen;
	compressionBlockSizeBytes = DEFAULT_BLOCK_SIZE;

	/***********************************************/
	/* Parse command line parameters if they exist */
	/***********************************************/
	if( (argc == 3) && (strlen(argv[1]) < 300) )
	{
		strcpy(inputfname,argv[1]);
		numIterations =  atoi(argv[2]);
	}
	else
	{
		/* Wrong # of arugments */
		printf("Error in arguments: [Fname] [NumIter]\n");
		return -1;
	}

	/* Determine Read buffersize, needs to be a multiple of block size */
	G_RD_BUFFER_SIZE = (BUFFER_SIZE/compressionBlockSizeBytes) * (compressionBlockSizeBytes);


	/* Force Max Filesize to 512MBytes */
	if(fileSize > G_RD_BUFFER_SIZE)
		fileSize = G_RD_BUFFER_SIZE;


	/* Allocate memory buffers */
	inputBuffer = (unsigned char*) malloc(BUFFER_SIZE);
	if(inputBuffer == NULL)
	{
		printf("Error allocating memory.\n");
		return -1;
	}
	outputBuffer = (unsigned char*) malloc(BUFFER_SIZE + (size_t)(0.1*BUFFER_SIZE));
	if(outputBuffer == NULL)
	{
		printf("Error allocating memory.\n");
		return -1;
	}
	dictMem = (char*) malloc(1024*1024*1);	/* 1MB */
	if(dictMem == NULL)
	{
		printf("Error allocating memory.\n");
		return -1;
	}

	/* Open the file for reading */
    infile = fopen(inputfname,"rb");
	if(infile == NULL)
	{
		printf("Error opening Handle to input file\n");
		return -1;
	}

	/* Fill the Input Buffer For Compresssion */
	numRead = fread(inputBuffer,1,G_RD_BUFFER_SIZE,infile);
	fclose(infile);

	printf("Beginning Compression of %s, Size = %d bytes, Iter=%d.\n",inputfname,numRead,numIterations);


	numberOfInputBlocks = 0;

	for(aa=0;aa<numIterations;aa++)
	{
		printf("Running iteration %d\n", aa);
		blockFullCount = 0;
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
			lzo1x_1_15_compress(pInputBuffer, blockSize, 
								outputBuffer, &outLength, dictMem);
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
			totalOutlen+=outLength;			//Update Length of Output Data
			pInputBuffer+=blockSize;					//Advance Input Pointer

			fileSize-= blockSize;				//Update Remaining Filesize
			bufferedBytes -= blockSize;					//Update Remaining Bytes in the current memory read buffer
			if(fileSize < blockSize)			//Update Block Size when only a remainder size exists
				blockSize = fileSize;
		}
	}

	FILE* out = fopen(OUTPUT_FILE_NAME,"w");
	fwrite(outputBuffer,1,totalOutlen,out);
	fclose(out);

	free(inputBuffer);
	free(dictMem);
	free(outputBuffer);

	return 0;
}