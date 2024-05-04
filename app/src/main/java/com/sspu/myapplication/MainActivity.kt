package com.sspu.myapplication

import android.content.pm.PackageManager
import android.widget.Button
import android.graphics.BitmapFactory
import android.os.Bundle
import android.os.Environment
import android.widget.ImageView
import androidx.appcompat.app.AppCompatActivity
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import okio.ByteString
import android.util.Log
import androidx.core.content.ContextCompat
import okhttp3.Response
import java.io.File
import java.io.IOException
import android.Manifest
import androidx.core.app.ActivityCompat
import com.google.firebase.FirebaseApp
import com.google.firebase.database.ktx.database
import com.google.firebase.ktx.Firebase
import kotlinx.coroutines.*




class MainActivity: AppCompatActivity() {
    private lateinit var imageView: ImageView
    private lateinit var webSocket: WebSocket
    private val client by lazy { OkHttpClient() }
    private var lastUpdateTime = 0L
    private val updateInterval = 100 // 100ms，每100毫秒更新一次UI
    private val database = Firebase.database("https://sspu-thesis-default-rtdb.europe-west1.firebasedatabase.app/")
    private val colorRef = database.getReference("trackingColor/color")

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // Initialize Firebase
        FirebaseApp.initializeApp(this)
        setContentView(R.layout.activity_main)
        imageView = findViewById<ImageView>(R.id.imageView)
        checkAndRequestPermissions() // 在这里调用权限检查
        initializeWebSocket()

        val pinkButton: Button = findViewById(R.id.buttonPink)
        pinkButton.setOnClickListener {
            updateColor("pink")
        }

        val blueButton: Button = findViewById(R.id.buttonBlue)
        blueButton.setOnClickListener {
            updateColor("blue")
        }

        val greenButton: Button = findViewById(R.id.buttonGreen)
        greenButton.setOnClickListener {
            updateColor("green")
        }
        val whiteButton: Button = findViewById(R.id.buttonWhite)
        whiteButton.setOnClickListener {
            updateColor("white")
        }

        val blackButton: Button = findViewById(R.id.buttonBlack)
        blackButton.setOnClickListener {
            updateColor("black")
        }

        val orangeButton: Button = findViewById(R.id.buttonOrange)
        orangeButton.setOnClickListener {
            updateColor("orange")
        }

        val exitButton: Button = findViewById(R.id.buttonExit)
        exitButton.setOnClickListener {
            finishAndRemoveTask() // 结束任务并移除
        }

    }


    companion object {
        private const val PERMISSIONS_REQUEST_WRITE_EXTERNAL_STORAGE = 1
    }
    private fun updateColor(color: String) {
        // 更新Firebase数据库中的颜色
        Log.d("MainActivity", "Attempting to update color to $color")
        colorRef.setValue(color)
            .addOnSuccessListener {
                Log.d("MainActivity", "Color updated to $color")
            }
            .addOnFailureListener { exception ->
                // 在这里增加更详细的错误日志
                Log.e("MainActivity", "Failed to update color to $color. Error: ${exception.message}", exception)
            }
    }

    private fun checkAndRequestPermissions() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.WRITE_EXTERNAL_STORAGE)
            != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this,
                arrayOf(Manifest.permission.WRITE_EXTERNAL_STORAGE),
                PERMISSIONS_REQUEST_WRITE_EXTERNAL_STORAGE)
        }
    }
    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        when (requestCode) {
            PERMISSIONS_REQUEST_WRITE_EXTERNAL_STORAGE -> {
                if (grantResults.isNotEmpty() && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                    Log.d("MainActivity", "Write storage permission granted")
                } else {
                    Log.d("MainActivity", "Write storage permission denied")
                }
            }
        }
    }


    private fun initializeWebSocket() {
        val request = Request.Builder().url("ws://10.0.2.2:8765").build() // Make sure the URL is correct
        webSocket = client.newWebSocket(request, object : WebSocketListener() {

            override fun onOpen(webSocket: WebSocket, response: Response) {
                super.onOpen(webSocket, response)
                Log.d("WebSocket", "WebSocket connection established")
            }
            private var messageCount = 0

            override fun onMessage(webSocket: WebSocket, bytes: ByteString) {
                messageCount++
                Log.d("WebSocket", "onMessage count: $messageCount")
                val byteArray = bytes.toByteArray()

                // 在IO线程解码Bitmap，并在主线程更新ImageView
                GlobalScope.launch(Dispatchers.IO) {
                    val bitmap = BitmapFactory.decodeByteArray(byteArray, 0, byteArray.size)
                    withContext(Dispatchers.Main) {
                        imageView.setImageBitmap(bitmap)
                        Log.d("WebSocket", "Image view updated with new frame.")
                    }
                }

                // 异步保存接收到的字节数据到文件
                GlobalScope.launch(Dispatchers.IO) {
                    val filename = "frame_${System.currentTimeMillis()}.jpg"
                    saveByteArrayToFile(byteArray, filename)
                    Log.d("WebSocket", "Received image saved to file: $filename")
                }
            }

            private fun saveByteArrayToFile(byteArray: ByteArray, filename: String) {
                try {
                    val file = File(getExternalFilesDir(null), filename)
                    file.writeBytes(byteArray)
                    Log.d("WebSocket", "Image file saved: ${file.absolutePath}")
                } catch (e: IOException) {
                    Log.e("WebSocket", "Error saving image file", e)
                }
            }





            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Log.e("WebSocket", "Error on WebSocket", t)
                response?.let {
                    Log.e("WebSocket", "Response: $it")
                }            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                super.onClosing(webSocket, code, reason)
                Log.d("WebSocket", "Closing: $code / $reason")
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                super.onClosed(webSocket, code, reason)
                Log.d("WebSocket", "Closed: $code / $reason")
            }
        })
        // Don't shutdown the client as it will cancel all ongoing operations and new requests.
        // client.dispatcher.executorService.shutdown()
    }

    private fun saveByteArrayToFile(imageBytes: ByteArray, fileName: String = "receivedImage.jpg") {
        try {
            val file = File(getExternalFilesDir(null), fileName)
            file.writeBytes(imageBytes)
            Log.d("WebSocket", "Image file saved: ${file.absolutePath}")
        } catch (e: Exception) {
            Log.e("WebSocket", "Error saving image file", e)
        }
    }


    private fun updateImageView(imageBytes: ByteArray) {
        val currentTime = System.currentTimeMillis()
        if (currentTime - lastUpdateTime > updateInterval) {
            val bitmap = BitmapFactory.decodeByteArray(imageBytes, 0, imageBytes.size)
            if (bitmap != null) {
                imageView.setImageBitmap(bitmap)
                lastUpdateTime = currentTime
            } else {
                Log.d("WebSocket", "Failed to decode bitmap")
            }
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        webSocket.close(1000, "Activity Destroyed")
    }
}
